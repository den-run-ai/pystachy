"""Serial opt + whole-lli instruction profiles of the actual Pystachy driver.

This is a scratch measurement controller, not a compiler modification. Whole
lli includes machine-code generation, program execution, runtime and GC work.
Instrumented wall times are diagnostics, not native performance measurements.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time

import measure


# Each role uses these same wrapper files for warm and profile runs. Changing
# only the environment switch does not invalidate the driver's runtime cache.
WRAPPER = r'''
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback


def identity(path):
    path = Path(path)
    return {"path": str(path), "realpath": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def fd_identity(fd, destination=None):
    before = os.lseek(fd, 0, os.SEEK_CUR)
    digest = hashlib.sha256()
    offset = 0
    output = open(destination, "wb") if destination else None
    try:
        while True:
            chunk = os.pread(fd, 1024 * 1024, offset)
            if not chunk:
                break
            digest.update(chunk)
            if output:
                output.write(chunk)
            offset += len(chunk)
    finally:
        if output:
            output.close()
    after = os.lseek(fd, 0, os.SEEK_CUR)
    if before != after:
        raise RuntimeError("capturing an inherited descriptor changed its offset")
    return {"fd": fd, "target": os.readlink("/proc/self/fd/" + str(fd)),
            "offset_before": before, "offset_after": after, "bytes": offset,
            "sha256": digest.hexdigest(),
            "capture": str(destination) if destination else None}


def pump(source, destination, fd, errors):
    try:
        with open(destination, "wb") as raw:
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break
                raw.write(chunk)
                rest = memoryview(chunk)
                while rest:
                    written = os.write(fd, rest)
                    rest = rest[written:]
    except BaseException:
        errors.append(traceback.format_exc())


def main():
    tool = Path(sys.argv[0]).name
    args = sys.argv[1:]
    real = Path(os.environ["PY996_JIT_REAL_LLVM"]) / tool
    directory = Path(os.environ["PY996_JIT_LOG_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    event = directory / (tool + "." + str(time.time_ns()) + "." + str(os.getpid()))
    version = "--version" in args
    profile = os.environ.get("PY996_JIT_PROFILE") == "1" and not version
    kind = "version" if version else "lli-whole" if tool == "lli" else (
        "opt-user" if any(a.startswith("-passes=") for a in args) else "opt-other")
    command = [str(real), *args]
    record = {"tool": tool, "kind": kind, "profiled": profile,
              "wrapper_pid": os.getpid(), "wrapper": identity(sys.argv[0]),
              "tool_identity": identity(real), "cwd": os.getcwd(),
              "original_command": command, "complete": False}
    stdout = Path(str(event) + ".stdout")
    stderr = Path(str(event) + ".stderr")
    record.update(stdout_file=str(stdout), stderr_file=str(stderr))
    save(Path(str(event) + ".json"), record)
    try:
        if profile and tool == "opt":
            outputs = [args[i + 1] for i, value in enumerate(args[:-1]) if value == "-o"]
            inputs = []
            for i, value in enumerate(args):
                path = Path(value)
                if not value.startswith("-") and value not in outputs and path.is_file():
                    item = identity(path)
                    capture = Path(str(event) + ".input-" + str(i) + path.suffix)
                    capture.write_bytes(path.read_bytes())
                    item["capture"] = str(capture)
                    inputs.append(item)
            record["inputs"] = inputs
        if profile and tool == "lli":
            if "/dev/fd/9" not in args:
                raise RuntimeError("actual driver did not pass its user module as /dev/fd/9")
            record["optimized_user_bitcode"] = fd_identity(9, Path(str(event) + ".optimized.bc"))
            record["loaded_runtime"] = fd_identity(8)
        if profile:
            callgrind = str(event) + ".callgrind"
            log = str(event) + ".valgrind.log"
            command = [os.environ["PY996_JIT_VALGRIND"], "--tool=callgrind",
                       "--compress-strings=no", "--compress-pos=no", "--dump-instr=yes",
                       "--callgrind-out-file=" + callgrind, "--log-file=" + log,
                       *command]
            record.update(callgrind_file=callgrind, valgrind_log_file=log)
        record["executed_command"] = command
        save(Path(str(event) + ".json"), record)
        start = time.perf_counter()
        # Inherited driver descriptors 8 and 9 must survive both this wrapper
        # and Valgrind. Pipes merely tee bytes; tool arguments are unchanged.
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 close_fds=False)
        record["child_pid"] = child.pid
        errors = []
        threads = [threading.Thread(target=pump, args=(child.stdout, stdout, 1, errors)),
                   threading.Thread(target=pump, args=(child.stderr, stderr, 2, errors))]
        for thread in threads:
            thread.start()
        code = child.wait()
        for thread in threads:
            thread.join()
        record.update(returncode=code, wall_s=time.perf_counter() - start,
                      stream_errors=errors, complete=True)
        for name, path in (("stdout", stdout), ("stderr", stderr)):
            record[name] = identity(path)
        if profile and tool == "opt":
            record["outputs"] = [identity(path) for path in outputs if Path(path).is_file()]
        save(Path(str(event) + ".json"), record)
        if errors:
            raise RuntimeError("stream forwarding failed; see raw event record")
        if code < 0:
            signal.signal(-code, signal.SIG_DFL)
            os.kill(os.getpid(), -code)
        return code
    except BaseException:
        record["wrapper_error"] = traceback.format_exc()
        save(Path(str(event) + ".json"), record)
        raise


if __name__ == "__main__":
    sys.exit(main())
'''


def identity(path):
    path = Path(path)
    stat = path.stat()
    return {"path": str(path), "realpath": str(path.resolve()),
            "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "sha256": measure.digest(path)}


def snapshot(directory):
    return {str(path.relative_to(directory)): identity(path)
            for path in sorted(directory.rglob("*")) if path.is_file()}


def runtime_objects(cache):
    return {name: info for name, info in cache.items()
            if Path(name).suffix in (".bc", ".o", ".so", ".target")}


def run_record(command, cwd, env, prefix, timeout):
    """Keep raw output and failure records even when a command times out."""
    command = [str(part) for part in command]
    prefix.parent.mkdir(parents=True, exist_ok=True)
    stdout, stderr = Path(str(prefix) + ".stdout"), Path(str(prefix) + ".stderr")
    record = {"command": command, "cwd": str(cwd), "timeout_s": timeout,
              "stdout_file": str(stdout), "stderr_file": str(stderr)}
    start = time.perf_counter()
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            child = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                     start_new_session=True)
            record["pid"] = child.pid
            try:
                record["returncode"] = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                record["returncode"] = child.returncode
    except OSError as error:
        record["launch_error"] = repr(error)
        record["returncode"] = None
    record["wall_s"] = time.perf_counter() - start
    for name, path in (("stdout", stdout), ("stderr", stderr)):
        record[name] = path.read_bytes().decode("utf-8", errors="backslashreplace")
        record[name + "_identity"] = identity(path)
    measure.save(Path(str(prefix) + ".json"), record)
    return record


def succeeded(record):
    if record["returncode"] != 0 or record.get("timed_out"):
        raise RuntimeError("command failed; raw record: " + record["stdout_file"][:-7] + ".json")


def wrappers(directory):
    directory.mkdir(parents=True)
    source = "#!" + str(measure.PY) + "\n" + WRAPPER
    for tool in sorted(measure.LLVM.iterdir()):
        if tool.name in ("opt", "lli"):
            target = directory / tool.name
            target.write_text(source)
            target.chmod(0o755)
        elif tool.is_file():
            (directory / tool.name).symlink_to(tool)
    return {name: identity(directory / name) for name in ("opt", "lli")}


def invocations(directory):
    return [{"record_file": str(path), **json.loads(path.read_text())}
            for path in sorted(directory.glob("*.json"))]


def callgrind_ir(path):
    events, summary, totals = None, None, None
    with Path(path).open() as source:
        for line in source:
            if line.startswith("events:"):
                events = line.split()[1:]
            elif line.startswith("summary:"):
                summary = [int(value) for value in line.split()[1:]]
            elif line.startswith("totals:"):
                totals = [int(value) for value in line.split()[1:]]
    if not events or "Ir" not in events or summary is None or totals is None:
        raise ValueError("incomplete callgrind file: " + str(path))
    if summary != totals:
        raise ValueError("callgrind summary/totals differ: " + str(path))
    return summary[events.index("Ir")]


def version_records(directory, env):
    paths = {name: measure.LLVM / name
             for name in ("clang", "opt", "lli", "llvm-as", "llvm-link", "llvm-dis")}
    paths.update(python=measure.PY, valgrind=Path(shutil.which("valgrind") or "/missing-valgrind"))
    result = {}
    for name, path in paths.items():
        record = run_record([path, "--version"], measure.ROOT, env, directory / name, 30)
        succeeded(record)
        result[name] = {"identity": identity(path), "version": record}
    # The Debian valgrind launcher is a shell script; identify its native
    # launcher and the actual profiling engine, too.
    for path in (Path("/usr/bin/valgrind.bin"),
                 Path("/usr/libexec/valgrind/callgrind-amd64-linux"),
                 Path("/usr/libexec/valgrind/vgpreload_core-amd64-linux.so")):
        if path.exists():
            result[path.name] = {"identity": identity(path)}
    # opt and lli dynamically load LLVM. Retain ldd's unfiltered output and
    # hash every dependency whose absolute path it reports.
    for name in ("opt", "lli"):
        record = run_record(["ldd", paths[name]], measure.ROOT, env, directory / (name + "-ldd"), 30)
        succeeded(record)
        libraries = sorted(set(re.findall(r"(/\S+)\s+\(", record["stdout"])))
        result[name]["dependencies"] = {path: identity(path) for path in libraries}
        result[name]["ldd"] = record
    return result


def measure_role(role, args, directory, expected, result, report):
    target = directory / role
    target.mkdir()
    cache = target / "cache"
    cache.mkdir()
    wrapper_dir = target / "llvm"
    entry = {"role": role, "inputs_before": measure.manifest(role),
             "wrappers_before": wrappers(wrapper_dir), "cache_before": snapshot(cache),
             "phases": [], "complete": False}
    result["roles"][role] = entry
    env = measure.environment(role)
    env.update(PYSTACHY_LLVM=str(wrapper_dir), PYSTACHY_CACHE=str(cache),
               PY996_JIT_REAL_LLVM=str(measure.LLVM),
               PY996_JIT_VALGRIND=str(Path(shutil.which("valgrind")).resolve()))
    entry["environment_controls"] = {key: value for key, value in env.items()
                                     if key.startswith(("PYSTACHY_", "PY996_"))
                                     or key in ("PYTHONHASHSEED", "LD_PRELOAD", "LD_LIBRARY_PATH")}
    # A just-written opt wrapper would prevent the real driver's runtime-cache
    # publication. Wait only for that driver's documented 2-second settling rule.
    settle = max(0.0, 2.1 - (time.time() - max((wrapper_dir / name).stat().st_mtime
                                               for name in ("opt", "lli"))))
    entry["wrapper_settle_wait_s"] = settle
    measure.save(report, result)
    if settle:
        time.sleep(settle)
    command = [measure.PY, measure.ROLES[role] / "pystachy.py", "run",
               measure.SOURCES / "bench/smoke/text.py", "fnmatch", str(args.n)]
    warm_cache = None
    for phase in ("warm-build", "warm-reuse", "profile"):
        print(role, phase, flush=True)
        logs = target / phase / "tools"
        logs.mkdir(parents=True)
        env.update(PY996_JIT_LOG_DIR=str(logs), PY996_JIT_PROFILE="1" if phase == "profile" else "0")
        record = run_record(command, measure.ROLES[role], env, target / phase / "driver", args.timeout)
        calls = invocations(logs)
        current_cache = snapshot(cache)
        item = {"phase": phase, "driver": record, "tool_invocations": calls,
                "cache_after": current_cache, "stdout_matches_cpython": record["stdout"] == expected}
        entry["phases"].append(item)
        measure.save(report, result)
        succeeded(record)
        if record["stdout"] != expected:
            raise ValueError(role + " " + phase + " stdout differs from CPython")
        if any(not call.get("complete") or call.get("returncode") != 0
               or call.get("wrapper_error") or call.get("stream_errors") for call in calls):
            raise ValueError(role + " " + phase + " has a failed tool invocation")
        if phase != "warm-build":
            kinds = sorted(call["kind"] for call in calls if call["kind"] != "version")
            if kinds != ["lli-whole", "opt-user"]:
                raise ValueError(role + " " + phase + " did not reuse a warm runtime: " + repr(kinds))
        if phase == "warm-reuse":
            warm_cache = runtime_objects(current_cache)
            if not warm_cache or not any(name.endswith(".bc") for name in warm_cache):
                raise ValueError(role + " runtime cache was not populated")
        if phase == "profile":
            if warm_cache != runtime_objects(current_cache):
                raise ValueError(role + " runtime objects changed during profile")
            profiled = [call for call in calls if call["profiled"]]
            if sorted(call["kind"] for call in profiled) != ["lli-whole", "opt-user"]:
                raise ValueError(role + " profile lacks exactly one opt and one lli profile")
            item["instruction_counts"] = {call["kind"]: callgrind_ir(call["callgrind_file"])
                                          for call in profiled}
            item["instruction_counts"]["combined"] = sum(item["instruction_counts"].values())
            for call in profiled:
                call["callgrind_identity"] = identity(call["callgrind_file"])
                call["valgrind_log_identity"] = identity(call["valgrind_log_file"])
            lli = next(call for call in profiled if call["kind"] == "lli-whole")
            opt = next(call for call in profiled if call["kind"] == "opt-user")
            captured = lli["optimized_user_bitcode"]
            if len(opt.get("outputs", [])) != 1 or opt["outputs"][0]["sha256"] != captured["sha256"]:
                raise ValueError(role + " opt output differs from captured lli input")
            bitcode = Path(captured["capture"])
            llvm_ir = bitcode.with_suffix(".ll")
            disassembly = run_record([measure.LLVM / "llvm-dis", bitcode, "-o", llvm_ir],
                                     measure.ROLES[role], env, target / phase / "llvm-dis", 30)
            item["llvm_dis"] = disassembly
            measure.save(report, result)
            succeeded(disassembly)
            text = llvm_ir.read_text()
            item["optimized_user_code"] = {"bitcode": identity(bitcode), "llvm_ir": identity(llvm_ir),
                                            "llvm_lines": len(text.splitlines()),
                                            "defined_functions": len(re.findall(r"^define ", text, re.M)),
                                            "note": "Captured with pread on fd9 before lli; disassembled after the profiled driver completed."}
            print(role, item["instruction_counts"], flush=True)
        measure.save(report, result)
    entry["inputs_after"] = measure.manifest(role)
    entry["wrappers_after"] = {name: identity(wrapper_dir / name) for name in ("opt", "lli")}
    if entry["inputs_before"] != entry["inputs_after"] or entry["wrappers_before"] != entry["wrappers_after"]:
        raise ValueError(role + " compiler inputs or wrapper files changed during measurement")
    entry["complete"] = True
    measure.save(report, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roles", nargs="+", choices=measure.ROLES)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--timeout", type=int, default=900, help="bounded seconds per driver invocation")
    parser.add_argument("--output", type=Path, help="new evidence directory; must not already exist")
    args = parser.parse_args()
    if args.n <= 0 or args.timeout <= 0 or len(args.roles) != len(set(args.roles)):
        parser.error("n and timeout must be positive; roles must be unique")
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = (args.output or measure.OUT / ("jit-fnmatch-" + str(args.n) + "-" + stamp)).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = directory / "report.json"
    source = measure.SOURCES / "bench/smoke/text.py"
    result = {"controller": identity(Path(__file__)), "helper": identity(Path(measure.__file__)),
              "command": sys.argv, "python": sys.version, "platform": platform.platform(),
              "affinity": sorted(os.sched_getaffinity(0)), "mode": "fnmatch", "n": args.n,
              "source": identity(source), "role_order": args.roles, "roles": {}, "complete": False,
              "scope": "opt: actual user optimization; lli-whole: JIT machine-code generation plus program, runtime and GC execution. No startup-only claim.",
              "timing_note": "All wall times are diagnostics under instrumentation or hosted compilation, not native timing results.",
              "raw_output_note": "All stdout/stderr, returncodes and Valgrind logs are retained without filtering; version invocations bypass profiling."}
    measure.save(report, result)
    print("JIT evidence:", directory, flush=True)
    try:
        env = measure.environment(args.roles[0])
        result["tools"] = version_records(directory / "metadata", env)
        oracle = run_record([measure.PY, source, "fnmatch", str(args.n)], measure.SOURCES,
                            measure.environment("baseline"), directory / "cpython", 180)
        result["cpython"] = oracle
        measure.save(report, result)
        succeeded(oracle)
        for role in args.roles:
            measure_role(role, args, directory, oracle["stdout"], result, report)
        if result["controller"] != identity(Path(__file__)) or result["helper"] != identity(Path(measure.__file__)):
            raise ValueError("controller changed during measurement")
        if result["source"] != identity(source):
            raise ValueError("benchmark source changed during measurement")
        result["complete"] = True
    except Exception as error:
        result["error"] = repr(error)
        measure.save(report, result)
        print("FAILED:", error, "Raw evidence:", report, file=sys.stderr, flush=True)
        return 1
    measure.save(report, result)
    print("Complete:", report, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
