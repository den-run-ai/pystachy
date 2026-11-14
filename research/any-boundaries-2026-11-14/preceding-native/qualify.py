"""Run an explicitly supplied completed native compiler against isolated sources."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys


ROOT = Path("/workspace/scratch/6e931c3f8732/boundary-qualification")
HERE = Path(__file__).resolve().parent
PYTHON = Path("/workspace/scratch/c2b093657c17/dev-venv/bin/python3.13")
LLVM = Path("/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18")
EXPECTED_SOURCE = "6cb04cef038e059f8cba5f491b075f5553c58f1a"


def main() -> None:
    assert len(sys.argv) == 2, "pass the completed bootstrap binary explicitly"
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert source == EXPECTED_SOURCE, source
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    supplied = Path(sys.argv[1]).resolve()
    compiler = ROOT / "pystachy"
    shutil.copy2(supplied, compiler)
    binary_sha = hashlib.sha256(compiler.read_bytes()).hexdigest()
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env.update({
        "PYSTACHY_HOME": str(ROOT),
        "PYSTACHY_LLVM": str(LLVM / "bin"),
        "PYSTACHY_CACHE": str(HERE / "runtime-cache"),
        "PYSTACHY_JOBS": "2",
        "LD_LIBRARY_PATH": str(LLVM / "lib"),
        "PATH": str(PYTHON.parent) + os.pathsep + env["PATH"],
    })
    expected = subprocess.run([str(PYTHON), str(HERE / "consumer.py")], env=env, capture_output=True)
    assert expected.returncode == 0 and not expected.stderr, expected.stderr
    (HERE / "cpython.out").write_bytes(expected.stdout)
    results = []

    def checked(label: str, command: list[str], settings: dict[str, str]) -> None:
        run = subprocess.run(command, cwd=ROOT, env={**env, **settings}, capture_output=True)
        (HERE / (label + ".out")).write_bytes(run.stdout)
        (HERE / (label + ".err")).write_bytes(run.stderr)
        row = {"label": label, "rc": run.returncode, "stdout_matches": run.stdout == expected.stdout, "stderr_empty": not run.stderr}
        results.append(row)
        print(json.dumps(row), flush=True)
        assert run.returncode == 0 and run.stdout == expected.stdout and not run.stderr, row

    checked("consumer-jit", [str(compiler), "run", str(HERE / "consumer.py")], {})
    checked("consumer-jit-gc", [str(compiler), "run", str(HERE / "consumer.py")], {"PYSTACHY_GC_STRESS_PROGRAM": "1"})
    executable = HERE / "consumer.exe"
    build = subprocess.run([str(compiler), "build", str(HERE / "consumer.py"), "-o", str(executable)], cwd=ROOT, env=env, capture_output=True)
    (HERE / "consumer-build.out").write_bytes(build.stdout)
    (HERE / "consumer-build.err").write_bytes(build.stderr)
    assert build.returncode == 0 and not build.stdout and not build.stderr, build.stderr
    checked("consumer-aot", [str(executable)], {})
    checked("consumer-aot-gc", [str(executable)], {"PYSTACHY_GC_STRESS": "1"})

    paths = (HERE / "suite-files.txt").read_text().splitlines()
    for label, selected, settings in [
        ("native-suite", paths, {}),
        ("native-suite-gc", [p for p in paths if "/programs/" in p], {"PYSTACHY_GC_STRESS_PROGRAM": "1"}),
    ]:
        with (HERE / (label + ".log")).open("w") as log:
            run = subprocess.run(["tests/run.sh", str(compiler), "jit aot", *selected], cwd=ROOT, env={**env, **settings}, stdout=log, stderr=subprocess.STDOUT)
        tail = (HERE / (label + ".log")).read_text().splitlines()[-4:]
        row = {"label": label, "cases": len(selected), "rc": run.returncode, "tail": tail}
        results.append(row)
        print(json.dumps(row), flush=True)
        assert run.returncode == 0, row
    report = {"source": source, "supplied_binary": str(supplied), "binary_sha256": binary_sha, "workers": 2, "results": results}
    (HERE / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
