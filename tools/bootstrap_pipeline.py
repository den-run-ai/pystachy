#!/usr/bin/env python3
"""Opt-in bootstrap experiment; every run builds two native compilers afresh."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_identity(root):
    paths = [root / p for p in ("pystachy.py", "runtime.py", "runtime.c")]
    for directory in ("src", "lib", "ryu", "mpz"):
        paths.extend(p for p in (root / directory).rglob("*")
                     if p.suffix in (".py", ".c", ".h") and p.is_file())
    files = {str(p.relative_to(root)): digest(p) for p in sorted(set(paths))}
    return {"sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), "files": files}


def tool_identity(python, llvm):
    found = {"python": shutil.which(python) or python}
    for name in ("clang", "opt", "llvm-as", "llvm-link", "ld.lld"):
        found[name] = str(Path(llvm) / name) if llvm else shutil.which(name)
    identities, hashes = {}, {}
    for name, value in found.items():
        if value and Path(value).is_file():
            path = Path(value).resolve()
            if path not in hashes:
                hashes[path] = digest(path)
            identities[name] = {"path": str(path), "sha256": hashes[path]}
        else:
            identities[name] = None
    return identities


def host_state():
    state = {"load_average": list(os.getloadavg()), "logical_cpus": os.cpu_count()}
    try:
        state["affinity_cpus"] = sorted(os.sched_getaffinity(0))
    except AttributeError:
        pass
    for name, filename in (("cpu", "/proc/cpuinfo"), ("memory", "/proc/meminfo"),
                           ("cpu_quota", "/sys/fs/cgroup/cpu.max"),
                           ("memory_limit", "/sys/fs/cgroup/memory.max")):
        try:
            value = Path(filename).read_text()
            if name == "cpu":
                value = next((line.split(":", 1)[1].strip() for line in value.splitlines()
                              if line.startswith("model name")), platform.processor())
            elif name == "memory":
                value = "\n".join(line for line in value.splitlines() if line.startswith(("MemTotal:", "MemAvailable:")))
            state[name] = value.strip()
        except OSError:
            state[name] = None
    return state


def plan(args, work):
    """All six witnesses have distinct producing compiler invocations."""
    compilers = [[args.python, "pystachy.py"], [str(work / "pystachy1")], [str(work / "pystachy2")]]
    nodes = []

    def add(name, argv, deps, slots=1, opt=2):
        nodes.append({"name": name, "command": argv, "dependencies": deps,
                      "slots": slots, "aot_opt": opt, "status": "pending"})

    for i in (1, 2):
        command = compilers[i - 1] + ["build", "pystachy.py", "-o", str(work / f"pystachy{i}")]
        if args.variant != "baseline":
            command += ["--emit-ir", str(work / f"stage{i}.ll")]
        if i == 1 and args.stage1_split:
            command = [args.python, str(args.root / "bench/compiler_host/self_pipeline.py"),
                       "--hosted", "--root", str(args.root), "--llvm", args.llvm,
                       "--work", str(work / "stage1-pipeline"), "--report", str(work / "stage1-pipeline.json"),
                       "--jobs", str(args.build_jobs), "--partitions", str(args.stage1_split),
                       "--opt", str(args.stage1_opt), "--cache", str(work / "cache"),
                       "--output", str(work / "pystachy1"), "--emit-ir", str(work / "stage1.ll"),
                       "--caller-witnesses"]
            if args.runtime_overlap:
                command.append("--overlap")
        add(f"build{i}", command, ["build1"] if i == 2 else [], args.build_jobs,
            args.stage1_opt if i == 1 else 2)
    for i in range(1 if args.variant == "baseline" else 3, 4):
        add(f"ir{i}", compilers[i - 1] + ["ir", "pystachy.py", "-o", str(work / f"stage{i}.ll")], ["build2"])
    for i in (1, 2, 3):
        add(f"rt{i}", compilers[i - 1] + ["rt", "runtime.py", "-o", str(work / f"rt{i}.ll")],
            [f"build{i - 1}"] if i > 1 else [])
    if args.variant != "optimized":
        for previous, node in zip(nodes, nodes[1:]):
            node["dependencies"] = [previous["name"]]
    return nodes


def signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def run_nodes(nodes, args, work, env):
    running = {}
    started = time.monotonic()
    interrupted = 0

    def stop(signum, frame):
        nonlocal interrupted
        interrupted = signum

    handlers = {s: signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}

    def finish(pid, status, usage):
        proc, node, log, began = running.pop(pid)
        proc.returncode = os.waitstatus_to_exitcode(status)
        log.close()
        node.update(returncode=proc.returncode, wall_seconds=time.monotonic() - began,
                    cpu_seconds=usage.ru_utime + usage.ru_stime,
                    max_rss_bytes=usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                    status="passed" if proc.returncode == 0 else "failed")

    try:
        while any(n["status"] == "pending" for n in nodes) or running:
            if interrupted:
                raise KeyboardInterrupt
            passed = {n["name"] for n in nodes if n["status"] == "passed"}
            used = sum(job[1]["slots"] for job in running.values())
            for node in nodes:
                if node["status"] != "pending" or not set(node["dependencies"]) <= passed or used + node["slots"] > args.jobs:
                    continue
                child_env = dict(env, PYSTACHY_BUILD_JOBS=str(node["slots"]),
                                 PYSTACHY_LTO_PARTITIONS=str(args.partitions if node["name"].startswith("build") else 0),
                                 PYSTACHY_AOT_OPT=str(node["aot_opt"]))
                node["environment"] = {k: v for k, v in child_env.items() if k.startswith("PYSTACHY_")}
                node["log"] = str(work / (node["name"] + ".log"))
                log = open(node["log"], "wb")
                try:
                    proc = subprocess.Popen(node["command"], cwd=args.root, env=child_env,
                                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                except BaseException:
                    log.close()
                    node["status"] = "failed"
                    raise
                began = time.monotonic()
                node.update(status="running", started_seconds=began - started, pid=proc.pid)
                running[proc.pid] = (proc, node, log, began)
                used += node["slots"]
                # A signal during Popen must not raise until its child is owned.
                if interrupted:
                    raise KeyboardInterrupt
            if not running:
                raise RuntimeError("bootstrap dependency graph did not complete")
            for pid, (_, node, _, began) in list(running.items()):
                done, status, usage = os.wait4(pid, os.WNOHANG)
                if done:
                    finish(pid, status, usage)
                    if node["status"] != "passed":
                        # Kill descendants even if the direct child has already exited.
                        signal_group(pid, signal.SIGTERM)
                        signal_group(pid, signal.SIGKILL)
                        raise RuntimeError(f"{node['name']} failed; see {node['log']}")
                elif time.monotonic() - began > args.timeout:
                    node["timed_out"] = True
                    raise RuntimeError(f"{node['name']} exceeded {args.timeout:g} seconds")
            time.sleep(0.02)
    finally:
        # Ignore repeated signals while bounded cleanup reaps every owned child.
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        for pid in running:
            signal_group(pid, signal.SIGTERM)
        # Nested worker controllers use 0.25 s to drain their descendants and
        # publish failure evidence. Give that cleanup time before the fallback.
        deadline = time.monotonic() + 0.75
        while running and time.monotonic() < deadline:
            for pid in list(running):
                done, status, usage = os.wait4(pid, os.WNOHANG)
                if done:
                    signal_group(pid, signal.SIGKILL)
                    finish(pid, status, usage)
            if running:
                time.sleep(0.01)
        for pid in list(running):
            signal_group(pid, signal.SIGKILL)
            _, status, usage = os.wait4(pid, 0)
            finish(pid, status, usage)
        for node in nodes:
            if node["status"] == "pending":
                node["status"] = "blocked"
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        if interrupted:
            raise SystemExit(128 + interrupted)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--llvm", default=os.getenv("PYSTACHY_LLVM", ""))
    parser.add_argument("--variant", choices=("baseline", "retained-ir", "optimized"), default="retained-ir")
    parser.add_argument("--jobs", type=int, default=1, help="total compiler/LLVM worker budget")
    parser.add_argument("--build-jobs", type=int, default=1, help="slots reserved per native build")
    parser.add_argument("--partitions", type=int, default=0)
    parser.add_argument("--stage1-opt", type=int, choices=(0, 1, 2), default=2)
    parser.add_argument("--stage1-split", type=int, default=0,
                        help="research: early-split temporary self-build, final build retains the driver")
    parser.add_argument("--runtime-overlap", action="store_true",
                        help="research: overlap whole cold runtime and hosted frontend in the split first stage")
    parser.add_argument("--runtime-c-cache", action="store_true", help="enable the independent runtime C bitcode cache")
    parser.add_argument("--timing", action="store_true", help="retain driver stage timings in each command log")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per command")
    parser.add_argument("--output", type=Path, required=True, help="parent directory for a fresh private run")
    args = parser.parse_args(argv)
    if not 1 <= args.build_jobs <= args.jobs <= 64 or not 0 <= args.partitions <= args.build_jobs or args.timeout <= 0:
        parser.error("require 1 <= build-jobs <= jobs <= 64, 0 <= partitions <= build-jobs, timeout > 0")
    if args.stage1_split and (not 1 <= args.stage1_split <= 8 or args.build_jobs > 8
                              or args.variant == "baseline" or not args.runtime_c_cache):
        parser.error("stage1-split needs retained witnesses, runtime-c-cache, 1..8 partitions and at most 8 build jobs")
    if args.runtime_overlap and (not args.stage1_split or args.build_jobs < 2):
        parser.error("runtime-overlap needs stage1-split and at least two build jobs")
    args.root = args.root.resolve()
    args.python = str(Path(shutil.which(args.python) or args.python).resolve())
    if not args.llvm:
        for directory in ("/usr/lib/llvm-18/bin", "/opt/homebrew/opt/llvm@20/bin", "/usr/local/opt/llvm@20/bin"):
            if all((Path(directory) / t).is_file() for t in ("clang", "opt", "llvm-as", "llvm-link")):
                args.llvm = directory
                break
    if args.llvm:
        args.llvm = str(Path(args.llvm).resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.variant + "-", dir=args.output.resolve()))
    (work / "cache").mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update(PYSTACHY_HOME=str(args.root), PYSTACHY_CACHE=str(work / "cache"))
    if args.runtime_c_cache:
        env["PYSTACHY_RUNTIME_C_CACHE"] = "1"
    if args.timing:
        env["PYSTACHY_TIMING"] = "1"
    if args.llvm:
        env["PYSTACHY_LLVM"] = args.llvm
    nodes = plan(args, work)
    report = {"schema_version": 1, "variant": args.variant, "status": "failed", "work_directory": str(work),
              "options": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              "platform": platform.platform(), "host_before": host_state(), "steps": nodes, "fixed_points": {},
              "planned_work": {"native_builds": 2, "compiler_frontend_emissions": 5 if args.variant == "baseline" else 3,
                               "compiler_fixed_point_witnesses": 3, "runtime_fixed_point_witnesses": 3}}
    start = time.monotonic()
    code = 1
    try:
        report["source"] = source_identity(args.root)
        report["tools"] = tool_identity(args.python, args.llvm)
        report["harness_sha256"] = digest(Path(__file__))
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.root, capture_output=True, text=True)
        report["commit"] = commit.stdout.strip() if commit.returncode == 0 else None
        status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"],
                                cwd=args.root, capture_output=True, text=True)
        report["git_status"] = status.stdout.splitlines() if status.returncode == 0 else None
        report["setup_seconds"] = time.monotonic() - start
        command_start = time.monotonic()
        try:
            run_nodes(nodes, args, work, env)
        finally:
            report["command_phase_seconds"] = time.monotonic() - command_start
        for prefix in ("stage", "rt"):
            hashes = [digest(work / f"{prefix}{i}.ll") for i in (1, 2, 3)]
            report["fixed_points"][prefix] = {"sha256": hashes, "identical": len(set(hashes)) == 1}
            if len(set(hashes)) != 1 or any((work / f"{prefix}{i}.ll").stat().st_size == 0 for i in (1, 2, 3)):
                raise RuntimeError(f"{prefix} IR fixed point failed")
        report["binaries"] = {f"pystachy{i}": {"sha256": digest(work / f"pystachy{i}"),
                                "bytes": (work / f"pystachy{i}").stat().st_size} for i in (1, 2)}
        if source_identity(args.root) != report["source"]:
            raise RuntimeError("source files changed during bootstrap")
        report["status"], code = "passed", 0
    except (OSError, RuntimeError) as exc:
        report["error"] = str(exc)
    except (KeyboardInterrupt, SystemExit) as exc:
        report["error"] = "bootstrap interrupted"
        code = exc.code if isinstance(exc, SystemExit) else 130
        report["status"] = "interrupted"
    finally:
        report["wall_seconds"] = time.monotonic() - start
        report["verification_seconds"] = max(0, report["wall_seconds"] - report.get("setup_seconds", report["wall_seconds"])
                                             - report.get("command_phase_seconds", 0))
        report["wall_note"] = "end-to-end setup + command phase + verification; command phase includes scheduling and cancellation cleanup"
        report["host_after"] = host_state()
        report["cpu_seconds"] = sum(n.get("cpu_seconds", 0) for n in nodes)
        report["largest_command_max_rss_bytes"] = max((n.get("max_rss_bytes", 0) for n in nodes), default=0)
        report["rss_note"] = "wait4 maximum per command, including reaped descendants; not aggregate concurrent peak RSS"
        (work / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(work / "report.json", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
