"""Exact-head native overflow checks after the combined bootstrap."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

repo, proof_path, output = map(lambda value: Path(value).resolve(), sys.argv[1:4])
proof = json.loads(proof_path.read_text())
digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
git = lambda *args: subprocess.check_output(["git", *args], cwd=repo, text=True).strip()
assert proof["status"] == "complete" and proof["source_identity_stable"]
assert git("rev-parse", "HEAD") == proof["commit"]
assert git("rev-parse", "HEAD^{tree}") == proof["tree"]
assert not git("status", "--porcelain=v1")
assert digest(repo / "pystachy") == proof["artifacts"]["pystachy"]["sha256"]
output.mkdir(exist_ok=False)
cases = [
    "tests/programs/language/recursion_checked_leaf.py",
    "tests/programs/language/recursion_after_call.py",
    "tests/programs/exceptions/exc_recursion_unwind.py",
    "tests/programs/exceptions/exc_recursion_contexts.py",
    "tests/programs/generators/gen_recursion_guard.py",
    "tests/programs/runtime/rt_recursion_scoped_files.py",
]
environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
environment.update(PYSTACHY_LLVM=os.environ["PYSTACHY_LLVM"], PYSTACHY_CACHE=str(output / "cache"),
                   PYSTACHY_JIT_INLINE="0", PYSTACHY_JOBS="2", PYTHONDONTWRITEBYTECODE="1", LC_ALL="C")
record = dict(status="running", commit=proof["commit"], tree=proof["tree"],
              bootstrap_sha256=digest(proof_path), compiler_sha256=digest(repo / "pystachy"),
              harness_sha256=digest(__file__), cases={path: digest(repo / path) for path in cases},
              environment={key: value for key, value in environment.items() if key.startswith("PYSTACHY_")},
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), observations=[])

def save():
    temporary = output / "report.json.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(output / "report.json")

def run(name, command, extra=None):
    env = dict(environment, **(extra or {}))
    row = dict(name=name, command=command, extra_environment=extra or {}, status="running")
    record["observations"].append(row)
    save()
    start = time.monotonic()
    with (output / (name + ".log")).open("wb") as log:
        process = subprocess.Popen(command, cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            row["returncode"] = process.wait(timeout=180)
        except BaseException:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            row["status"] = "interrupted_or_timeout"
            save()
            raise
    row.update(seconds=time.monotonic() - start, log_sha256=digest(output / (name + ".log")),
               status="passed" if row["returncode"] == 0 else "failed")
    save()
    assert row["returncode"] == 0, row
    return row

save()
try:
    for number, case in enumerate(cases):
        target = output / (str(number) + ".ll")
        row = run("ir-" + str(number), [str(repo / "pystachy"), "ir", case, "-o", str(target)])
        definitions = [line for line in target.read_text().splitlines()
                       if line.startswith("define internal ") and re.search(r"@pys\.recursion\.(check|enter)\(", line)]
        assert definitions and all("alwaysinline" not in line for line in definitions), (case, definitions)
        row.update(raw_ir_sha256=digest(target), guard_definitions=definitions)
        save()
    run("jit-aot", ["tests/run.sh", "./pystachy", "jit aot", *cases])
    assert "12 passed, 0 failed" in (output / "jit-aot.log").read_text()
    run("gc-scoped-file", ["tests/run.sh", "./pystachy", "jit", cases[-1]],
        {"PYSTACHY_GC_STRESS_PROGRAM": "1"})
    assert "1 passed, 0 failed" in (output / "gc-scoped-file.log").read_text()
    assert git("rev-parse", "HEAD") == proof["commit"] and not git("status", "--porcelain=v1")
    assert digest(repo / "pystachy") == record["compiler_sha256"]
    assert all(digest(repo / path) == sha for path, sha in proof["after"].items())
    assert all(digest(repo / path) == sha for path, sha in record["cases"].items())
    record.update(status="passed", native_executions=13, source_identity_stable=True)
except BaseException as error:
    record.update(status="failed", error=repr(error))
    raise
finally:
    save()
print(json.dumps({key: record[key] for key in ["status", "commit", "native_executions"]}))
