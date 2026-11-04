"""Compare the adapted command's argv, streams, status and file effects on CPython, JIT and AOT."""
from dataclasses import dataclass
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
ENTRY = ROOT / "examples/json_repair/repair.py"
RAW = '{name: "café", values: [true, null,],}'.encode()
UTF8 = '{"name": "café", "values": [true, null]}\n'.encode()
ESCAPED = b'{"name": "caf\\u00e9", "values": [true, null]}'


@dataclass
class Case:
    args: list[str]
    status: int = 0
    stdin: bytes = RAW
    source: bytes = RAW
    source_after: bytes | None = None
    output: bytes | None = None
    stdout: bytes | None = b""


CASES = [
    Case([], stdout=UTF8),
    Case(["", "--output", ""], stdout=UTF8),
    Case(["-o", "out", "--ensure_ascii", "--", "-input"], output=ESCAPED),
    Case(["-input", "--inline"], 2),  # Leading hyphen needs --.
    Case(["--inline", "--ensure_ascii", "--", "-input"], source_after=ESCAPED),
    Case(["-i", "--output", "out", "--", "-input"], 1),
    Case(["--inline"], 1),
    Case(["missing"], 1),
    Case(["--strict", "--inline", "--", "-input"], 1, source=b'"a": 1}'),
    Case(["--skip-json-loads"], stdin=b"42", stdout=b'""\n'),
    Case(["-o"], 2),
    Case(["--indent=4"], 2),
    Case(["--help"], stdout=None),
]


def run_case(command, case, env):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "-input").write_bytes(case.source)
        result = subprocess.run(command + case.args, input=case.stdin, cwd=root, env=env,
                                capture_output=True, timeout=120)
        files = {path.name: path.read_bytes() for path in root.iterdir()}
    expected = {"-input": case.source if case.source_after is None else case.source_after}
    if case.output is not None:
        expected["out"] = case.output
    if result.returncode != case.status or files != expected:
        raise ValueError(f"{case.args}: exit={result.returncode}, files={files!r}, stderr={result.stderr!r}")
    if case.stdout is not None and result.stdout != case.stdout:
        raise ValueError(f"{case.args}: expected {case.stdout!r}, got {result.stdout!r}")
    return result.stdout, result.stderr


def main():
    pinned = (ROOT / ".python-version").read_text().strip()
    if platform.python_implementation() != "CPython" or platform.python_version() != pinned:
        sys.exit(f"Use CPython {pinned} for the argparse oracle")
    compiler = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "pystachy").resolve()
    env = os.environ | {"PYTHONPATH": str(ROOT / "ports"), "PYSTACHY_PATH": str(ROOT / "ports"),
                        "PYSTACHY_HOME": str(ROOT), "COLUMNS": "80", "LC_ALL": "C", "PYTHONUTF8": "1"}
    aot_env = env.copy()
    if env.get("PYSTACHY_GC_STRESS_PROGRAM"):
        aot_env["PYSTACHY_GC_STRESS"] = env["PYSTACHY_GC_STRESS_PROGRAM"]
    with tempfile.TemporaryDirectory() as directory:
        exe = Path(directory) / "repair"
        subprocess.run([compiler, "build", ENTRY, "-o", exe], env=env, check=True, timeout=120)
        for case in CASES:
            oracle = run_case([sys.executable, "-m", "json_repair"], case, env)
            for mode, command, run_env in [("JIT", [compiler, "run", ENTRY], env), ("AOT", [exe], aot_env)]:
                actual = run_case(command, case, run_env)
                if actual != oracle:
                    raise ValueError(f"{mode} {case.args}: expected {oracle!r}, got {actual!r}")
    print(f"json_repair CLI: {len(CASES)} process cases matched CPython {pinned} in JIT and AOT")


if __name__ == "__main__":
    main()
