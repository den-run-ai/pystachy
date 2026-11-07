#!/usr/bin/env python3
"""Check comparison variants against the source with the verifying adapter.

This is a correctness smoke check, not the benchmark timing harness. Time fields
are discarded; state, drawing call counts, operation hashes and UI scenarios
must agree before any timing comparison is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build import AUTO_MODES, MODES, OPTIONAL_MODES, SENSITIVITY_BASELINES
from typed_codegen import NOEXCEPT_HELPERS, with_scalar_noexcept

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent
WORKLOADS = ("simulate", "ui", "submit", "poll", "frame", "ffi")
RUN = "from benchmark_workload import run;import sys;run(sys.argv[1],int(sys.argv[2]),7,2)"
ERRORS = r'''
from ctypes import ArgumentError
import raylib_backend as r
cases = [
    (r._rect,(2**33,0,1,1,0xFFFFFFFF),OverflowError),
    (r._rect,(1.5,0,1,1,0xFFFFFFFF),(TypeError,ArgumentError)),
    (r._begin,(-1,),OverflowError),
    (r._begin,(2**32,),OverflowError),
    (r._text,("a\0b",0,0,18,0xFFFFFFFF),ValueError),
    (r.Window,(1,1,"bad"),ValueError),
]
for function, args, expected in cases:
    try:
        function(*args)
    except expected:
        pass
    else:
        raise AssertionError((function,args,expected))
print("native errors: signed/unsigned ranges, noninteger, NUL, dimensions passed")
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--library-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--modes", nargs="+", choices=(*MODES, *OPTIONAL_MODES), default=MODES,
                        help="variants to check; the CPython source reference is always included")
    args = parser.parse_args()
    records = []
    expected_results = {}
    reference_headless = None
    test_path = ROOT / "tests/programs/apps/miniui_headless.py"
    test = "from pathlib import Path;p=Path(" + repr(str(test_path)) + ");exec(compile(p.read_text(),str(p),'exec'))"
    for variant in ("cpython_source", *args.modes):
        directory = SOURCE if variant == "cpython_source" else args.output.resolve() / variant
        if variant != "cpython_source":
            metadata = json.loads((directory / "build-metadata.json").read_text())
            assert metadata["mode"] == variant, (variant, "incorrect build label")
            for filename, expected_hash in metadata["source_sha256"].items():
                actual_hash = hashlib.sha256((SOURCE / filename).read_bytes()).hexdigest()
                assert actual_hash == expected_hash, (variant, filename, "stale build source")
            if variant in AUTO_MODES:
                assert metadata["infer_types"] is None, (variant, "default inference not enabled")
                baseline = args.output.resolve() / SENSITIVITY_BASELINES[variant]
                if (baseline / "build-metadata.json").is_file():
                    for filename in ("miniui.py", "raylib_backend.py", "benchmark_workload.py"):
                        assert (directory / filename).read_bytes() == (baseline / filename).read_bytes(), filename
                    if variant == "cython_native_auto":
                        assert (directory / "raylib_backend.pyx").read_bytes() == (baseline / "raylib_backend.pyx").read_bytes()
            if variant == "cython_typed_noexcept":
                assert metadata["infer_types"] is False
                assert metadata["native_noexcept_helpers"] == list(NOEXCEPT_HELPERS)
                baseline = args.output.resolve() / "cython_typed"
                # If the primary typed build exists, the sensitivity must differ
                # only in the explicit scalar-helper exception declarations.
                if (baseline / "build-metadata.json").is_file():
                    for filename in ("miniui.pyx", "miniui.pxd", "benchmark_workload.pyx",
                                     "benchmark_workload.pxd"):
                        assert (directory / filename).read_bytes() == (baseline / filename).read_bytes(), filename
                    expected_backend = with_scalar_noexcept((baseline / "raylib_backend.pyx").read_text())
                    assert (directory / "raylib_backend.pyx").read_text() == expected_backend
                    expected_declarations = (baseline / "raylib_backend.pxd").read_text()
                    for helper in NOEXCEPT_HELPERS:
                        lines = expected_declarations.splitlines()
                        expected_declarations = "\n".join(
                            line + " noexcept" if line.startswith("cdef ") and " " + helper + "(" in line else line
                            for line in lines) + "\n"
                    assert (directory / "raylib_backend.pxd").read_text() == expected_declarations
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, [directory, SOURCE, ROOT / "tools/rt_cpython"])),
                   LD_LIBRARY_PATH=str(args.library_dir.resolve()))
        def execute(code: str, *arguments: str, env=env, variant=variant) -> str:
            result = subprocess.run([sys.executable, "-c", code, *arguments], env=env,
                                    cwd=ROOT, text=True, capture_output=True, timeout=60)
            if result.returncode:
                raise RuntimeError(variant + " failed:\n" + result.stdout + result.stderr)
            return result.stdout
        modules = execute("import json,miniui,raylib_backend,benchmark_workload;print(json.dumps({k:v.__file__ for k,v in [('miniui',miniui),('raylib_backend',raylib_backend),('benchmark_workload',benchmark_workload)]}))")
        for filename in json.loads(modules).values():
            assert Path(filename).parent == directory, (variant, filename, directory)
        headless = execute(test)
        if reference_headless is None:
            reference_headless = headless
        else:
            assert headless == reference_headless, (variant, "headless difference")
        execute(ERRORS)
        for particles in (150, 2000):
            for workload in WORKLOADS:
                output = execute(RUN, workload, str(particles))
                lines = [line for line in output.splitlines() if line.startswith("RESULT ")]
                assert len(lines) == 1, (variant, output)
                fields = lines[0].split()
                normalized = fields[:5] + fields[6:]
                key = (particles, workload)
                if variant == "cpython_source":
                    expected_results[key] = normalized
                else:
                    assert normalized == expected_results[key], (variant, normalized, expected_results[key])
                records.append({"variant": variant, "particles": particles, "mode": workload,
                                "fields_without_time": normalized})
        print(variant + ": source imports, 10 UI scenarios, boundary errors and 12 workload checks passed", flush=True)
    result = {"python": sys.version, "variants": list(args.modes), "checks": records, "headless": reference_headless,
              "adapter": str(args.library_dir.resolve()), "all_passed": True}
    if args.record:
        args.record.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
