"""Opt-in correctness check for ndarray_blas; requires NumPy and LP64 libblas.so.3.

The CPython FFI twin calls the same library using copied arrays. JIT/AOT borrow
native lists and need neither CPython nor NumPy at execution time. This checker
does not benchmark that copying path. It runs every view/alias/bounds case in
normal and GC-stressed native modes and compares every result with NumPy.
"""

import argparse
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def parse(stdout):
    values = {}
    errors = {}
    for line in stdout.splitlines():
        tag, literal = line.split(" ", 1)
        record = ast.literal_eval(literal)
        if tag == "CASE":
            name, shape, data = record
            if name in values:
                raise ValueError("duplicate case: " + name)
            values[name] = (shape, data)
        elif tag == "ERROR":
            name, message = record
            if name in errors:
                raise ValueError("duplicate error case: " + name)
            errors[name] = message
        else:
            raise ValueError("unexpected output: " + line)
    if len(values) != 24 or len(errors) != 15:
        raise ValueError("missing case/error records")
    return values, errors


def run(command, env):
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{shlex.join(command)} failed ({result.returncode})\n{result.stdout[-2000:]}{result.stderr[-4000:]}")
    return result.stdout


def loaded_blas_paths():
    maps = Path("/proc/self/maps")
    if not maps.is_file():
        return []
    paths = set()
    for line in maps.read_text().splitlines():
        pieces = line.split()
        if pieces and pieces[-1].startswith("/"):
            path = pieces[-1]
            if "libblas" in path or "libopenblas" in path:
                paths.add(path)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=f"{shlex.quote(sys.executable)} {shlex.quote(str(ROOT / 'pystachy.py'))}")
    parser.add_argument("--stress", type=int, default=7, help="collect every N allocations in extra JIT/AOT runs (default7)")
    parser.add_argument("--json", type=Path, help="optional verification report")
    args = parser.parse_args()
    if args.stress < 1:
        parser.error("--stress must be positive")
    compiler = [str((ROOT / part).resolve()) if not part.startswith("-") and (ROOT / part).is_file() else part
                for part in shlex.split(args.compiler)]
    if not compiler:
        parser.error("--compiler must not be empty")
    # The fixed binding is LP64 by contract; symbol presence alone cannot detect
    # an ILP64 replacement. No portable CBLAS ABI-introspection API exists.
    library = ctypes.CDLL("libblas.so.3")
    _ = library.cblas_dgemm
    if ctypes.sizeof(ctypes.c_int) != 4 or ctypes.sizeof(ctypes.c_double) != 8:
        raise RuntimeError("this example requires 32-bit C int and 64-bit double")
    import numpy as np

    sys.path.insert(0, str(ROOT / "tools" / "rt_cpython"))
    from blas_cases import cases

    expected = {}
    for name, a, b in cases():
        # Independently interpret the NDArray views. Singleton-axis strides do
        # not affect indexing and may exceed NumPy's byte-stride range.
        def numpy_view(value):
            data = np.asarray(value.data, dtype=np.float64)
            strides = tuple(0 if dim <= 1 else stride * 8 for dim, stride in zip(value.shape, value.strides))
            return np.ndarray(tuple(value.shape), dtype=np.float64, buffer=data,
                              offset=value.offset * 8, strides=strides)

        expected[name] = numpy_view(a) @ numpy_view(b)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "tools" / "rt_cpython"), str(HERE)])
    for name in ("PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM"):
        env.pop(name, None)
    source = HERE / "blas_cases.py"
    reference_errors = None
    report = {"binding": "libblas.so.3:cblas_dgemm", "abi": "explicit LP64: 32-bit int, 64-bit double",
              "loaded_blas_paths": loaded_blas_paths(), "numpy": np.__version__,
              "source_sha256": hashlib.sha256((HERE / "ndarray_blas.py").read_bytes()).hexdigest(),
              "cases": len(expected), "invalid_inputs": 15, "runs": {}}
    with tempfile.TemporaryDirectory(prefix="ndarray-blas-check-") as directory:
        executable = Path(directory) / "cases"
        run(compiler + ["build", str(source), "-o", str(executable)], env)
        commands = [
            ("cpython", [sys.executable, str(source)], {}),
            ("jit", compiler + ["run", str(source)], {}),
            ("aot", [str(executable)], {}),
            ("jit_gc", compiler + ["run", str(source)], {"PYSTACHY_GC_STRESS_PROGRAM": str(args.stress)}),
            ("aot_gc", [str(executable)], {"PYSTACHY_GC_STRESS": str(args.stress)}),
        ]
        for name, command, extra in commands:
            values, errors = parse(run(command, env | extra))
            if reference_errors is None:
                reference_errors = errors
            if errors != reference_errors or values.keys() != expected.keys():
                raise AssertionError(f"{name}: cases or rejection messages differ")
            maximum = 0.0
            for label, target in expected.items():
                shape, data = values[label]
                if shape != list(target.shape) or len(data) != target.size:
                    raise AssertionError(f"{name}/{label}: result shape or size differs")
                actual = np.asarray(data, dtype=np.float64).reshape(shape)
                if not np.isfinite(actual).all():
                    raise AssertionError(f"{name}/{label}: nonfinite result")
                np.testing.assert_allclose(actual, target, rtol=1e-12, atol=1e-12)
                if target.size:
                    maximum = max(maximum, float(np.max(np.abs(actual - target))))
            report["runs"][name] = {"max_abs_error_vs_numpy": maximum, "gc_allocation_interval": extra}
            print(f"{name}: {len(values)} matrix cases and {len(errors)} invalid inputs passed")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("LP64 CBLAS verification passed; no performance claim is made by this check.")


if __name__ == "__main__":
    main()
