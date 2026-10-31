"""Recovered research harness helpers; fresh observations, no historical relabeling."""
import hashlib
import json
import os
import signal
from pathlib import Path
import statistics
import subprocess
import time

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_identity(directory):
    directory = Path(directory).resolve()
    paths = [directory / name for name in ("pystachy.py", "runtime.c", "runtime.py", "pyext.c", "pyembed.c", "Makefile")]
    for folder in ("src", "lib", "mpz", "ryu"):
        paths += [path for path in (directory / folder).rglob("*") if path.is_file() and path.suffix in (".py", ".c", ".h")]
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=directory, text=True).strip()
    return {"directory": str(directory), "commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "git_status": git("status", "--porcelain=v1"),
            "input_sha256": {str(path.relative_to(directory)): digest(path) for path in sorted(set(paths)) if path.is_file()}}

class ReplayFailure(RuntimeError):
    def __init__(self, message, record=None):
        super().__init__(message)
        self.record = record

def run(command, cwd, env, timeout=240):
    command = list(map(str, command))
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as error:
        # Stop only this command's owned group, including opt/lli descendants.
        # A timed-out native driver must not leave a profiler contaminating the
        # next phase or another agent's measurements.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        record = {"command": command, "cwd": str(cwd), "stdout": stdout, "stderr": stderr,
                  "returncode": process.returncode, "process_group_terminated": True,
                  "wall_seconds": time.monotonic() - started}
        if isinstance(error, subprocess.TimeoutExpired):
            record["timeout"] = timeout
            raise ReplayFailure("timeout", record) from error
        raise
    record = {"command": command, "cwd": str(cwd), "returncode": process.returncode, "stdout": stdout,
              "stderr": stderr, "wall_seconds": time.monotonic() - started}
    if process.returncode:
        raise ReplayFailure("nonzero exit", record)
    return record

def parse(record, expected=None):
    try:
        lines = record["stdout"].splitlines()
        prefix, value = lines[0].split()
        checksum = int(value)
        samples = [list(map(int, row.split())) for row in lines[1:]]
        valid = prefix == "warm" and len(samples) == 7 and all(len(row) == 2 and row[0] == checksum and row[1] > 0 for row in samples)
        valid = valid and (expected is None or checksum == expected)
    except (ValueError, IndexError):
        valid = False
    if not valid:
        raise ReplayFailure("kernel checksum/sample mismatch", record)
    record.update(checksum=checksum, sample_ns=[row[1] for row in samples], median_ns=statistics.median(row[1] for row in samples))
    return record

def save_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)
