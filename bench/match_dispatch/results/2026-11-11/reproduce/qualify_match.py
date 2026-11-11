"""Run the bounded-match final matrix through the repository's own harnesses."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
output = root.parent / "match-final-qualification"
output.mkdir(exist_ok=True)
positive = sorted(str(p.relative_to(root)) for p in root.glob("tests/programs/language/match_*.py"))
positive += sorted(str(p.relative_to(root)) for p in root.glob("tests/programs/inference/dynany_match*.py"))
positive += ["tests/programs/apps/match_dispatch_workloads.py", "tests/programs/generators/gen_match_dispatch.py"]
negative = sorted(str(p.relative_to(root)) for p in root.glob("tests/errors/language/match_*.py"))
negative += ["tests/errors/language/nested_match_guard.py", "tests/errors/library/lib_statistics_kde.py"]
cases = positive + negative
assert len(cases) == len(set(cases))
expected = 2 * len(positive) + len(negative)
report = {
    "status": "incomplete", "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip(),
    "compiler_sha256": hashlib.sha256((root / "pystachy").read_bytes()).hexdigest(),
    "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "python": sys.version, "positive_cases": positive, "negative_cases": negative,
    "input_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in cases},
    "steps": [],
}
environment = {key: value for key, value in os.environ.items()
               if not key.startswith("PYSTACHY_") or key == "PYSTACHY_LLVM"}
environment.pop("PYTHONPATH", None)
environment.pop("PYTHONHOME", None)
environment.update(PYSTACHY_HOME=str(root), PYSTACHY_JOBS="2", PYSTACHY_PROGRAM_CACHE="0",
                   PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYTHON=sys.executable,
                   PY=sys.executable, LC_ALL="C.UTF-8")


def save():
    (output / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")


def run(name, command, extra=None, expected_text=None, occurrences=1, timeout=600):
    env = dict(environment)
    env.update(extra or {})
    start = time.monotonic()
    result = subprocess.run(command, cwd=root, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    (output / f"{name}.log").write_text(result.stdout)
    passed = result.returncode == 0 and (expected_text is None or result.stdout.count(expected_text) == occurrences)
    report["steps"].append({"name": name, "command": command, "settings": extra or {},
                           "wall_s": time.monotonic() - start, "exit_status": result.returncode,
                           "expected_text": expected_text, "expected_occurrences": occurrences,
                           "passed": passed, "log": f"{name}.log"})
    save()
    print(name, "PASS" if passed else "FAIL", result.stdout[-700:].strip(), flush=True)
    if not passed:
        raise RuntimeError(f"{name} failed; see {output / (name + '.log')}")


save()
try:
    with tempfile.TemporaryDirectory(prefix="match-final-qualification-") as cache:
        environment["PYSTACHY_CACHE"] = cache
        base = ["sh", "tests/run.sh"]
        run("focused-native", base + [str(root / "pystachy"), "jit aot", *cases],
            expected_text=f"{expected} passed, 0 failed")
        run("focused-hosted", base + [shlex.join([sys.executable, "-m", "pystachy"]), "jit aot", *cases],
            expected_text=f"{expected} passed, 0 failed")
        run("focused-program-gc", base + [str(root / "pystachy"), "jit aot", *cases],
            {"PYSTACHY_GC_STRESS_PROGRAM": "1"}, f"{expected} passed, 0 failed")
        stress = ["tests/programs/language/match_condition_order.py",
                  "tests/programs/language/match_capture_staging.py",
                  "tests/programs/language/match_nested_dataclasses.py"]
        run("compiler-and-program-gc", base + [str(root / "pystachy"), "jit aot", *stress],
            {"PYSTACHY_GC_STRESS": "1000", "PYSTACHY_GC_STRESS_PROGRAM": "1"}, "6 passed, 0 failed")
        run("optimizer-off", base + [str(root / "pystachy"), "jit aot", *positive],
            {"PYSTACHY_OPT": "-all"}, f"{2 * len(positive)} passed, 0 failed")
        for mode in ("python_int", "dynany"):
            run(mode, [sys.executable, f"tools/{mode}_optin.py", "--compiler", "./pystachy",
                       "--jobs", "2", "--report", str(output / f"{mode}.json"), "--cases", *positive])
        run("combined-matrix", [sys.executable, str(root.parent / "check_match_matrix.py"), str(root)])
        run("example-pytest", [sys.executable, "tools/pytest_native_suites.py", "--suite", "match_dispatch",
                               "--compiler", "./pystachy", "--work-dir", "build/pytest-match-final",
                               "--json", str(output / "pytest-example.json")],
            expected_text=": passed (11 cases)", occurrences=2)
    report["status"] = "passed"
    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save()
except Exception as error:
    report["error"] = str(error)
    save()
    raise
