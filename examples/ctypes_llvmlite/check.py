"""Compare the ctypes consumer with llvmlite's original Python binding.

Run with a Python environment containing requirements.txt. The default check
runs CPython ctypes, Pystachy JIT/AOT and both native modes with GC stress.
--cpython-only checks the consumer and independent oracle without compiling.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile

import llvmlite
import llvmlite.binding as llvm


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "verify_ir.py"


def cases() -> list[tuple[str, bytes, int]]:
    return [
        ("empty", b"", 0),
        ("constant", b"define i64 @answer() { ret i64 42 }\n", 0),
        ("reward", b"""source_filename = "reward.py"
define double @reward(double %distance, double %energy) {
entry:
  %scaled = fmul double %energy, 2.000000e+00
  %score = fsub double %distance, %scaled
  ret double %score
}
""", 0),
        ("unicode", 'source_filename = "caf\u00e9.py"\ndefine i32 @value() { ret i32 -7 }\n'.encode(), 0),
        ("nul_terminator", b"define i32 @value() { ret i32 5 }\n\0not LLVM", 0),
        ("many_functions", "".join(f"define i64 @f{i}() {{ ret i64 {i} }}\n" for i in range(32)).encode(), 0),
        ("syntax", b"define i64 @broken( {\n", 1),
        ("undefined", b"define i64 @broken() { ret i64 %missing }\n", 1),
        ("dominance", b"""define i32 @broken(i1 %condition) {
entry:
  br i1 %condition, label %yes, label %no
yes:
  %x = add i32 1, 2
  br label %merge
no:
  br label %merge
merge:
  ret i32 %x
}
""", 2),
        ("phi_predecessor", b"""define i32 @broken() {
entry:
  br label %exit
exit:
  %x = phi i32 [ 1, %exit ]
  ret i32 %x
}
""", 2),
    ]


def oracle(source: bytes) -> tuple[int, bytes]:
    """Use the unmodified installed high-level API, independently of ctypes declarations."""
    with llvm.create_context() as context:
        try:
            module = llvm.parse_assembly(source.decode("utf-8"), context)
        except RuntimeError as error:
            prefix = "LLVM IR parsing error\n"
            diagnostic = str(error)
            if not diagnostic.startswith(prefix):
                raise
            return 1, diagnostic[len(prefix):].encode("utf-8")
        with module:
            try:
                module.verify()
            except RuntimeError as error:
                return 2, str(error).encode("utf-8")
            return 0, str(module).encode("utf-8")


def run(command: list[str], env: dict[str, str], source: bytes = b"") -> bytes:
    result = subprocess.run(command, input=source, cwd=ROOT, env=env,
                            capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{shlex.join(command)} exited {result.returncode}\n"
                           + result.stderr.decode("utf-8", "replace")[-5000:])
    if result.stderr:
        raise RuntimeError(f"{shlex.join(command)} wrote unexpected stderr: {result.stderr!r}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"),
                        help="compiler command, including an interpreter if hosted")
    parser.add_argument("--cpython-only", action="store_true")
    parser.add_argument("--repeat", type=int, default=16)
    parser.add_argument("--stress", type=int, default=1,
                        help="allocation interval for extra native GC-stress runs")
    parser.add_argument("--json", type=Path, help="write the completed verification report")
    args = parser.parse_args()
    if args.repeat < 1 or args.stress < 1:
        parser.error("--repeat and --stress must be positive")
    if llvmlite.__version__ != "0.46.0":
        raise RuntimeError("install the pinned llvmlite==0.46.0 before checking")
    library = Path(llvm.__file__).resolve().parent / "libllvmlite.so"
    if sys.platform != "linux" or not library.is_file():
        raise RuntimeError("this example currently requires the Linux libllvmlite.so wheel")

    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("--compiler must not be empty")
    env = os.environ.copy()
    for name in ("PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM", "PYTHONPATH", "PYSTACHY_PATH"):
        env.pop(name, None)
    env["PYSTACHY_HOME"] = str(ROOT)
    env["PYSTACHY_PROGRAM_CACHE"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LD_LIBRARY_PATH"] = str(library.parent) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    version = llvm.llvm_version_info
    packed_version = (version[0] << 16) | (version[1] << 8) | version[2]
    expected = {}
    for label, source, status in cases():
        result = oracle(source)
        if result[0] != status:
            raise AssertionError(f"oracle/{label}: expected status {status}, got {result[0]}")
        expected[label] = f"{packed_version}\n{result[0]}\n{result[1].hex()}\n".encode()

    report = {
        "llvmlite": llvmlite.__version__, "llvm": version,
        "python": sys.version, "platform": platform.platform(),
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "consumer_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "repetitions_per_case": args.repeat,
        "cases": {name: {"input_sha256": hashlib.sha256(source).hexdigest(), "status": status,
                          "output_sha256": hashlib.sha256(expected[name]).hexdigest()}
                  for name, source, status in cases()},
        "runs": {},
    }
    with tempfile.TemporaryDirectory(prefix="pystachy-ctypes-llvmlite-") as directory:
        executable = Path(directory) / "verify-ir"
        commands = [("cpython_ctypes", [sys.executable, "-I", str(SOURCE)], {})]
        if not args.cpython_only:
            run(compiler + ["build", str(SOURCE), "-o", str(executable)], env)
            commands += [
                ("jit", compiler + ["run", str(SOURCE)], {}),
                ("aot", [str(executable)], {}),
                ("jit_gc", compiler + ["run", str(SOURCE)], {"PYSTACHY_GC_STRESS_PROGRAM": str(args.stress)}),
                ("aot_gc", [str(executable)], {"PYSTACHY_GC_STRESS": str(args.stress)}),
            ]
        for mode, command, settings in commands:
            for name, source, _ in cases():
                actual = run(command + [str(args.repeat)], env | settings, source)
                if actual != expected[name]:
                    raise AssertionError(f"{mode}/{name}: byte output differs\n"
                                         f"expected {expected[name]!r}\nactual {actual!r}")
            report["runs"][mode] = {"cases": len(expected), "gc_settings": settings}
            print(f"{mode}: {len(expected)} cases x {args.repeat} lifecycles match upstream llvmlite")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print("Exact IR/diagnostic parity passed; this does not establish full llvmlite or Numba support.")


if __name__ == "__main__":
    main()
