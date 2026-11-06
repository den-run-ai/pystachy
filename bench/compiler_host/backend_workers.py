"""Research LLVM workers with transferable, hash-checked job directories.

Coordinator: --input LINKED.bc --partitions 4 --jobs 4 --work DIR --report JSON
Worker only: --worker DIR --llvm /matching/llvm/bin

Input must already link program and runtime, with the desired target/layout and
pys_plain value. Partitioning BEFORE optimization changes optimization scope. This is an
experiment, not ThinLTO or a production replacement for the driver's backend.
Workers use only the standard library and input.bc + job.json. They can execute
on another compatible machine after transport, but this harness does no transport.
Tool hashes do not yet cover the complete target/sysroot/shared-library identity;
these jobs are not a sufficient key for a cross-host shared object cache.

Use --inherited-group only inside a controller that owns the entire process group,
propagates failures and cleans up descendants. Direct invocations own their group.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time


LATE = ["-force-remove-attribute=pys_new:noinline",
        "-force-remove-attribute=pys_new:optnone", "-force-attribute=pys_new:alwaysinline"]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def identity(llvm):
    return {name: digest(llvm / name) for name in ("clang", "opt", "ld.lld")}


def group_members():
    """Living members of our own group, in the caller's PID namespace.

    Hosted Linux sessions can expose an outer /proc mount. Never pass its outer
    PID directly to kill(): NSpid maps it to the namespace used by os.kill().
    Workers must stay in this group; deliberate daemonization is unsupported.
    """
    if Path("/proc/self/stat").is_file():
        own = Path("/proc/self/stat").read_text()
        group = int(own[own.rfind(")") + 2:].split()[2])
        status = Path("/proc/self/status").read_text().splitlines()
        ids = next(line.split()[1:] for line in status if line.startswith("NSpid:"))
        depth = len(ids)
        members = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                stat = (entry / "stat").read_text()
                fields = stat[stat.rfind(")") + 2:].split()
                if fields[0] == "Z" or int(fields[2]) != group:
                    continue
                status = (entry / "status").read_text().splitlines()
                ids = next(line.split()[1:] for line in status if line.startswith("NSpid:"))
                if len(ids) == depth and int(ids[-1]) != os.getpid():
                    members.append(int(ids[-1]))
            except (OSError, ValueError, IndexError, StopIteration):
                continue
        return members
    with subprocess.Popen(["ps", "-A", "-o", "pid=,pgid="], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as listing:
        output, error = listing.communicate()
        if listing.returncode:
            raise RuntimeError(f"cannot enumerate owned process group: {error}")
        rows = output.splitlines()
    return [int(pid) for row in rows for pid, group in [row.split()]
            if int(group) == os.getpgrp() and int(pid) not in (os.getpid(), listing.pid)]


class Commands:
    """Bounded subprocess ownership without detached per-worker sessions.

    The coordinator owns one process group. LLVM commands inherit it, so an
    outer controller can still kill the entire build. Local cancellation also
    terminates/reaps siblings before returning and never starts queued work.
    """

    def __init__(self, measure=None, owns_group=True, cleanup_grace=0.25):
        if not math.isfinite(cleanup_grace) or not 0 <= cleanup_grace <= 5:
            raise ValueError("cleanup grace must be finite and from 0 to 5 seconds")
        self.measure = measure
        self.owns_group = owns_group
        self.cleanup_grace = cleanup_grace
        self.running = {}
        self.results = []
        self.interrupted = 0
        self.handlers = {}

    def __enter__(self):
        if self.owns_group and os.getpgrp() != os.getpid():
            os.setpgid(0, 0)
        # Prove enumeration is available before starting work.
        if self.owns_group:
            group_members()
        self.handlers = {sig: signal.signal(sig, self.stop) for sig in (signal.SIGINT, signal.SIGTERM)}
        return self

    def stop(self, signum, frame):
        # A signal during Popen must wait until the returned child is owned.
        self.interrupted = signum

    def check_signal(self):
        if self.interrupted:
            raise InterruptedError(f"backend interrupted by signal {self.interrupted}")

    def start(self, key, command, env, cwd):
        out, err = tempfile.TemporaryFile(), tempfile.TemporaryFile()
        start = time.monotonic()
        try:
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err)
        except BaseException:
            out.close()
            err.close()
            raise
        self.running[proc.pid] = {"process": proc, "key": key, "command": command, "out": out, "err": err,
                                  "start": start, "peak": 0, "processes": 0, "sampled": 0,
                                  "proc_pid": None, "load": list(os.getloadavg()),
                                  "timed_out": False, "cancelled": False}
        self.check_signal()
        if self.measure:
            self.running[proc.pid]["proc_pid"] = self.measure.proc_child_pid(proc.pid)

    def finish(self, pid, status, usage):
        state = self.running.pop(pid)
        proc = state["process"]
        proc.returncode = os.waitstatus_to_exitcode(status)
        data = {}
        for name in ("out", "err"):
            stream = state[name]
            stream.seek(0)
            data[name] = stream.read()
            stream.close()
        result = {"key": state["key"], "command": state["command"], "exit_code": proc.returncode,
                "timed_out": state["timed_out"], "cancelled": state["cancelled"],
                "wall_s": time.monotonic() - state["start"],
                "cpu_s": usage.ru_utime + usage.ru_stime,
                "sampled_process_tree_peak_rss_kib": state["peak"] or None,
                "wait4_max_process_rss_kib": usage.ru_maxrss,
                "sampled_max_processes": state["processes"], "load_before": state["load"],
                "proc_pid_resolved": state["proc_pid"] is not None, "load_after": list(os.getloadavg()),
                "stdout_sha256": hashlib.sha256(data["out"]).hexdigest(),
                "stderr_sha256": hashlib.sha256(data["err"]).hexdigest(),
                "stdout": data["out"].decode("utf-8", "backslashreplace"),
                "stderr": data["err"].decode("utf-8", "backslashreplace")}
        self.results.append(result)
        return result

    def run(self, commands, env, timeout, jobs=1, cwd=None):
        if not 1 <= jobs <= 8 or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("require 1..8 jobs and a positive finite timeout")
        pending = iter(commands)
        exhausted = False
        while self.running or not exhausted:
            self.check_signal()
            # Observe every completion before launching more work. The caller
            # can reject a failed result without any queued job being launched.
            ready = []
            for pid, state in list(self.running.items()):
                now = time.monotonic()
                if state["proc_pid"] is not None and now - state["sampled"] >= 0.01:
                    rss, count = self.measure.process_tree_rss(state["proc_pid"])
                    state["peak"] = max(state["peak"], rss)
                    state["processes"] = max(state["processes"], count)
                    state["sampled"] = now
                waited, status, usage = os.wait4(pid, os.WNOHANG)
                if waited:
                    ready.append(self.finish(pid, status, usage))
                elif now - state["start"] >= timeout:
                    state["timed_out"] = True
                    raise TimeoutError(f"backend command {state['key']} exceeded {timeout:g} seconds")
            yield from ready
            self.check_signal()
            while not exhausted and len(self.running) < jobs:
                try:
                    key, command = next(pending)
                except StopIteration:
                    exhausted = True
                    break
                self.start(key, command, env, cwd)
            if self.running:
                time.sleep(0.005)

    def execute(self, command, env, timeout, cwd=None):
        return next(self.run([(0, command)], env, timeout, cwd=cwd))

    def __exit__(self, exc_type, exc, tb):
        # All descendants share this exclusively owned group. TERM reaches
        # grandchildren even if their worker already exited. Keep the parent
        # alive to save a failure report and escalate only remaining members.
        for sig in self.handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            for state in self.running.values():
                state["cancelled"] = True
            members = group_members() if self.owns_group else list(self.running)
            if members and self.owns_group:
                os.killpg(os.getpgrp(), signal.SIGTERM)
            elif members:
                for state in self.running.values():
                    try:
                        state["process"].terminate()
                    except ProcessLookupError:
                        pass
            if members:
                deadline = time.monotonic() + self.cleanup_grace
                while members and time.monotonic() < deadline:
                    time.sleep(0.01)
                    if self.owns_group:
                        members = group_members()
                    else:
                        for pid in list(self.running):
                            waited, status, usage = os.wait4(pid, os.WNOHANG)
                            if waited:
                                self.finish(pid, status, usage)
                        members = list(self.running)
                for pid in members:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            for pid in list(self.running):
                _, status, usage = os.wait4(pid, 0)
                self.finish(pid, status, usage)
        finally:
            for sig, handler in self.handlers.items():
                signal.signal(sig, handler)
        if self.interrupted and exc is None:
            raise InterruptedError(f"backend interrupted by signal {self.interrupted}")


def validate_result(directory, expected_job_sha256):
    result = json.loads((directory / "result.json").read_text())
    if (digest(directory / "job.json") != expected_job_sha256
            or result.get("job_sha256") != expected_job_sha256):
        raise RuntimeError("worker result/job identity mismatch")
    output = directory / "output.o"
    job = json.loads((directory / "job.json").read_text())
    if job.get("input_sha256") != digest(directory / "input.bc"):
        raise RuntimeError("worker input changed after submission")
    if (result.get("complete") is not True or not output.is_file()
            or result.get("output_sha256") != digest(output)
            or result.get("output_bytes") != output.stat().st_size):
        raise RuntimeError("incomplete or altered worker output")
    return result


def worker(work, llvm):
    work, llvm = work.resolve(), llvm.resolve()
    # Retrying a directory must never expose an earlier successful output if
    # this attempt is rejected, interrupted or fails before its first step.
    for name in ("result.json", "output.o", "output.tmp.o"):
        (work / name).unlink(missing_ok=True)
    job = json.loads((work / "job.json").read_text())
    if job["version"] not in (1, 2) or job["input_sha256"] != digest(work / "input.bc"):
        raise RuntimeError("worker input/version mismatch")
    if (job["tool_sha256"] != identity(llvm) or job["opt"] not in (0, 1, 2, 3)
            or job["emit"] not in ("object", "bitcode")):
        raise RuntimeError("worker toolchain/options mismatch")
    # Version 2 binds the optimizer policy. Version 1 remains replayable only
    # without that field; old worker scripts must reject new policy-bearing jobs.
    inline_threshold = job.get("inline_threshold")
    if ((job["version"] == 1 and "inline_threshold" in job)
            or (job["version"] == 2 and "inline_threshold" not in job)
            or (inline_threshold is not None
                and (type(inline_threshold) is not int or not 0 <= inline_threshold <= 10000))):
        raise RuntimeError("worker inlining policy/version mismatch")
    inline_flags = [] if inline_threshold is None else ["-mllvm", "-inline-threshold=" + str(inline_threshold)]
    clang, opt, level = str(llvm / "clang"), str(llvm / "opt"), "-O" + str(job["opt"])
    steps = [
        ("optimize", [clang, level, *inline_flags, "-c", "-emit-llvm", "input.bc", "-o", "optimized.bc"]),
        ("late_inline", [opt, "-passes=forceattrs,always-inline", *LATE, "optimized.bc", "-o", "late.bc"]),
    ]
    if job["emit"] == "object":
        steps.append(("codegen", [clang, level, "-c", "-Xclang", "-disable-llvm-passes", "late.bc", "-o", "output.tmp.o"]))
    report = {"job_sha256": digest(work / "job.json"), "steps": [], "complete": False}
    for name, command in steps:
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        with (work / f"{name}.stdout").open("wb") as out, (work / f"{name}.stderr").open("wb") as err:
            completed = subprocess.run(command, cwd=work, stdout=out, stderr=err, check=False)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        report["steps"].append({"name": name, "command": command, "wall_s": time.monotonic() - start,
                                "cpu_s": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                                "exit_code": completed.returncode})
        write_json(work / "result.json", report)
        if completed.returncode:
            raise RuntimeError(f"worker {name} failed: {(work / (name + '.stderr')).read_text()[-2000:]}")
    if job["emit"] == "bitcode":
        shutil.copyfile(work / "late.bc", work / "output.tmp.o")
    (work / "output.tmp.o").replace(work / "output.o")
    report.update({"complete": True, "output_sha256": digest(work / "output.o"),
                   "output_bytes": (work / "output.o").stat().st_size})
    write_json(work / "result.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--partitions", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--lto-partitions", type=int, default=0)
    parser.add_argument("--opt", type=int, choices=(0, 1, 2, 3), default=2)
    parser.add_argument("--inline-threshold", type=int, help="research: optimizer inlining threshold (0..10000); default uses LLVM policy")
    parser.add_argument("--timeout", type=float, default=600, help="seconds per worker or tool command")
    parser.add_argument("--inherited-group", action="store_true",
                        help="run inside an outer controller's owned process group")
    parser.add_argument("--managed-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be a positive finite number")
    if args.inline_threshold is not None and not 0 <= args.inline_threshold <= 10000:
        parser.error("inlining threshold must be from 0 to 10000")
    if args.worker:
        if args.inline_threshold is not None:
            parser.error("worker replay takes its inlining policy from job.json")
        if args.managed_worker:
            worker(args.worker, args.llvm)
        else:
            # A detached replay has the same cancellation ownership as the
            # coordinator, without importing anything from the repository.
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(args.worker),
                       "--llvm", str(args.llvm), "--managed-worker"]
            with Commands(owns_group=not args.inherited_group) as scope:
                result = scope.execute(command, dict(os.environ), args.timeout)
                if result["exit_code"]:
                    raise RuntimeError(result["stderr"][-3000:])
        return 0
    if args.managed_worker:
        parser.error("managed-worker requires worker")
    if not args.input or not args.work or not args.report or not 1 <= args.jobs <= 8 or not 1 <= args.partitions <= 8:
        parser.error("coordinator needs input/work/report and jobs/partitions in 1..8")
    if not 0 <= args.lto_partitions <= args.jobs or (args.lto_partitions and args.partitions != 1):
        parser.error("LTO needs one whole input and no more codegen partitions than jobs")
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("measure", root / "bench/compiler_parallel/llvm_partitions.py")
    measure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(measure)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    llvm = args.llvm.resolve()
    source = args.input.resolve()
    env = dict(os.environ)
    start = time.monotonic()
    report = {"input_sha256": digest(source), "partitions": args.partitions, "jobs": args.jobs,
              "lto_partitions": args.lto_partitions, "opt": args.opt, "inline_threshold": args.inline_threshold,
              "timeout_s": args.timeout,
              "input_bytes": source.stat().st_size, "tool_sha256": identity(llvm),
              "worker_script_sha256": digest(__file__), "workers": [], "complete": False}
    write_json(args.report, report)
    scope = Commands(measure, owns_group=not args.inherited_group)
    code = 1
    try:
        with scope:
            if args.partitions == 1:
                parts = [source]
            else:
                result = scope.execute([str(llvm / "llvm-split"), str(source), "-j", str(args.partitions), "-o", str(work / "part-")], env, args.timeout)
                report["split"] = result
                measure.successful(result)
                parts = [work / f"part-{i}" for i in range(args.partitions)]
            jobs = []
            expected_jobs = {}
            for i, part in enumerate(parts):
                directory = work / f"worker-{i}"
                directory.mkdir()
                shutil.copyfile(part, directory / "input.bc")
                job = {"version": 2, "input_sha256": digest(part), "tool_sha256": report["tool_sha256"], "opt": args.opt,
                       "inline_threshold": args.inline_threshold, "emit": "bitcode" if args.lto_partitions else "object"}
                write_json(directory / "job.json", job)
                expected_jobs[directory] = digest(directory / "job.json")
                jobs.append(directory)
            report["transferred_input_bytes"] = sum((job / "input.bc").stat().st_size for job in jobs)
            write_json(args.report, report)
            commands = [(i, [sys.executable, str(Path(__file__).resolve()), "--worker", str(directory),
                              "--llvm", str(llvm), "--managed-worker"]) for i, directory in enumerate(jobs)]
            for result in scope.run(commands, env, args.timeout, jobs=args.jobs):
                i = result.pop("key")
                directory = jobs[i]
                result["partition"] = i
                if (directory / "result.json").is_file():
                    result["worker"] = json.loads((directory / "result.json").read_text())
                report["workers"].append(result)
                write_json(args.report, report)
                measure.successful(result)
                result["worker"] = validate_result(directory, expected_jobs[directory])
            report["workers"].sort(key=lambda row: row["partition"])
            # Stable partition order matters for reproducibility and layout.
            command = [str(llvm / "clang"), *[str(job / "output.o") for job in jobs], "-o", str(work / "compiler"), "-lm"]
            if args.lto_partitions:
                command += ["-fuse-ld=" + str(llvm / "ld.lld"), "-flto=full", "-Wl,--lto-newpm-passes=verify",
                            "-Wl,--lto-CGO" + str(args.opt), "-Wl,--lto-partitions=" + str(args.lto_partitions),
                            "-Wl,--threads=" + str(args.jobs)]
            report["link"] = scope.execute(command, env, args.timeout)
            measure.successful(report["link"])
            report.update({"complete": True, "compiler_sha256": digest(work / "compiler"),
                           "compiler_bytes": (work / "compiler").stat().st_size})
            code = 0
    except (OSError, RuntimeError, ValueError) as error:
        report["complete"] = False
        report["error"] = str(error)
        if scope.interrupted:
            code = 128 + scope.interrupted
    finally:
        report["wall_s"] = time.monotonic() - start
        report["commands"] = scope.results
        write_json(args.report, report)
        print(json.dumps({key: report[key] for key in ("wall_s", "complete")}), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
