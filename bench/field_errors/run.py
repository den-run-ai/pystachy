#!/usr/bin/env python3
"""Paired frontend/native-build measurements for the inherited-field error IR (#786)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import signal
import shutil
import statistics
import subprocess
import sys
import time


def hierarchy(count):
    # __eq__ dispatch makes an inherited specialization for every receiver. Its
    # other argument stays Base, exposing repeated concrete-name error selection.
    lines = ["class Base:", "    def __init__(self, ready: bool) -> None:",
             "        if ready:", "            self.value = 7",
             "    def __eq__(self, other: 'Base') -> bool:",
             "        return self.value == other.value"]
    for i in range(count):
        lines.extend([f"class C{i}(Base):", "    pass"])
    lines.extend(["def same(a: Base, b: Base) -> bool:", "    return a == b",
                  f"print(same(C0(True), C{count - 1}(True)))", ""])
    return "\n".join(lines)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revision(root):
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = subprocess.check_output(["git", "ls-files", "-z", "pystachy.py", "runtime.py", "runtime.c", "src", "lib"], cwd=root)
    digest = hashlib.sha256()
    for name in sorted(x for x in names.split(b"\0") if x):
        digest.update(name + b"\0" + bytes.fromhex(sha(root / os.fsdecode(name))))
    return {"commit": commit, "compiler_source_sha256": digest.hexdigest()}


def measured(command, root, env, prefix):
    started = time.perf_counter()
    timed_out = False
    interrupted = None
    with prefix.with_suffix(".stdout").open("wb") as out, prefix.with_suffix(".stderr").open("wb") as err:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=out, stderr=err, start_new_session=True)

        def expire(signum, frame):
            raise TimeoutError("compiler command exceeded 600 seconds")

        previous = signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, 600)
        try:
            _, status, usage = os.wait4(process.pid, 0)
        except BaseException as error:
            timed_out = isinstance(error, TimeoutError)
            interrupted = error
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _, status, usage = os.wait4(process.pid, 0)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        process.returncode = os.waitstatus_to_exitcode(status)
    rss_kib = usage.ru_maxrss / 1024 if sys.platform == "darwin" else usage.ru_maxrss
    row = {"wall_s": time.perf_counter() - started, "user_s": usage.ru_utime, "system_s": usage.ru_stime,
           "max_process_rss_kib": rss_kib, "returncode": process.returncode, "timed_out": timed_out,
           "stdout_sha256": sha(prefix.with_suffix(".stdout")), "stderr_sha256": sha(prefix.with_suffix(".stderr")),
           "command": command}
    prefix.with_suffix(".metrics.json").write_text(json.dumps(row, indent=2) + "\n")
    if interrupted is not None:
        raise interrupted
    if process.returncode or prefix.with_suffix(".stdout").stat().st_size or prefix.with_suffix(".stderr").stat().st_size:
        raise RuntimeError(f"compiler failed or emitted unexpected diagnostics: {prefix} (exit {process.returncode})")
    return row


def ir_stats(path):
    data = path.read_bytes()
    text = data.decode()
    return {"bytes": len(data), "lines": len(text.splitlines()), "sha256": sha(path),
            "select_instructions": len(re.findall(r"^\s+%[^\n]* = select i1 ", text, re.M)),
            "class_name_tables": text.count("@pys.field.names =")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="baseline checkout, with its own pystachy executable")
    parser.add_argument("--head", type=Path, required=True, help="candidate checkout, with its own pystachy executable")
    parser.add_argument("--output", type=Path, required=True, help="new directory for frozen inputs, logs and results.json")
    parser.add_argument("--hosted", action="store_true", help="use this Python interpreter on each checkout's pystachy.py")
    parser.add_argument("--sizes", type=int, nargs="+", default=[8, 32, 128])
    parser.add_argument("--samples", type=int, default=5, help="fresh frontend processes per revision and input")
    parser.add_argument("--builds", type=int, default=0, help="warm-runtime native builds per revision and input (opt in)")
    parser.add_argument("--cpu", type=int, help="Linux CPU on which to run all measurements")
    args = parser.parse_args()
    if sys.platform not in ("linux", "darwin"):
        parser.error("this harness supports Linux/macOS wait4 accounting")
    if min(args.sizes) < 1 or args.samples < 1 or args.builds < 0:
        parser.error("sizes/samples must be positive and builds must be nonnegative")
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    roots = {"base": args.base.resolve(), "head": args.head.resolve()}
    commands = {name: [sys.executable, str(root / "pystachy.py")] if args.hosted else [str(root / "pystachy")]
                for name, root in roots.items()}
    envs = {}
    for name, root in roots.items():
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") or k == "PYSTACHY_LLVM"}
        env.update(PYSTACHY_HOME=str(root), PYSTACHY_CACHE=str(target / (name + "-cache")))
        envs[name] = env
    doc = {"complete": False, "command": shlex.join(sys.argv), "python": sys.version, "platform": platform.platform(),
           "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
           "compiler_host": "CPython" if args.hosted else "native Pystachy", "samples": [], "inputs": {},
           "revisions": {name: revision(root) for name, root in roots.items()},
           "notes": ["Compiler preparation is excluded. Each frontend sample is a fresh process.",
                     "Native build samples include frontend, LLVM and linking, with a prewarmed per-revision runtime cache.",
                     "wait4 maximum RSS is the maximum individual process RSS (including waited children), not a concurrent aggregate.",
                     "Execution checks compare exact stdout/exit status with CPython; they are not runtime-throughput benchmarks."]}
    for name in roots:
        doc["revisions"][name]["command"] = commands[name]
        doc["revisions"][name]["version"] = subprocess.check_output([*commands[name], "--version"], cwd=roots[name], env=envs[name], text=True).strip()
        if not args.hosted:
            doc["revisions"][name]["executable_sha256"] = sha(Path(commands[name][0]))
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    clang = str(Path(llvm) / "clang") if llvm else shutil.which("clang")
    doc["clang"] = subprocess.check_output([clang, "--version"], text=True).splitlines()[0] if clang else None
    doc["tools"] = {}
    for name in ("clang", "opt", "llvm-link", "llvm-as", "llc"):
        tool = str(Path(llvm) / name) if llvm else shutil.which(name)
        if tool:
            doc["tools"][name] = {"path": tool, "sha256": sha(Path(tool)),
                                  "version": subprocess.check_output([tool, "--version"], text=True).splitlines()[0]}
    inputs = {f"hierarchy-{n}": hierarchy(n) for n in args.sizes}
    inputs["exact-class"] = """class Exact:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7

def read(obj: Exact) -> int:
    return obj.value
print(read(Exact(True)))
"""
    inputs["hierarchy-no-read"] = hierarchy(max(args.sizes)).replace("self.value == other.value", "self is other")
    inputs["sparse-read"] = hierarchy(1) + "".join(
        f"class Unrelated{i}:\n    pass\nclass UnrelatedChild{i}(Unrelated{i}):\n    pass\n"
        for i in range(max(args.sizes)))
    paths = {}
    for case, source in inputs.items():
        path = target / (case + ".py")
        path.write_text(source)
        paths[case] = path
        oracle = subprocess.run([sys.executable, str(path)], capture_output=True, check=True)
        if oracle.stderr:
            raise RuntimeError(f"unexpected CPython diagnostics: {case}")
        doc["inputs"][case] = {"sha256": sha(path), "source_bytes": path.stat().st_size, "oracle_stdout": oracle.stdout.decode()}
    def save():
        (target / "results.json").write_text(json.dumps(doc, indent=2) + "\n")
    save()
    try:
        if args.builds:
            for name in roots:
                measured([*commands[name], "build", str(paths["exact-class"]), "-o", str(target / (name + "-warm"))],
                         roots[name], envs[name], target / (name + "-warm-log"))
        for case, path in paths.items():
            for phase, count in [("frontend", args.samples), ("build", args.builds)]:
                for sample in range(count):
                    for name in (list(roots) if sample % 2 == 0 else list(reversed(roots))):
                        prefix = target / f"{case}-{phase}-{sample}-{name}"
                        output = prefix.with_suffix(".ll" if phase == "frontend" else ".exe")
                        command = [*commands[name], "ir" if phase == "frontend" else "build", str(path), "-o", str(output)]
                        row = {"case": case, "phase": phase, "sample": sample, "revision": name, "command": command,
                               **measured(command, roots[name], envs[name], prefix)}
                        if phase == "frontend":
                            row["ir"] = ir_stats(output)
                        else:
                            completed = subprocess.run([str(output)], capture_output=True, check=True, timeout=30)
                            if completed.stderr or completed.stdout.decode() != doc["inputs"][case]["oracle_stdout"]:
                                raise RuntimeError(f"output mismatch: {case} {name}")
                            row.update(executable_bytes=output.stat().st_size, executable_sha256=sha(output), output_matches=True)
                        doc["samples"].append(row)
                        save()
                        print(f"{case} {phase} {sample} {name}: {row['wall_s']:.4f}s", flush=True)
        for case in paths:
            for name in roots:
                hashes = {r["ir"]["sha256"] for r in doc["samples"]
                          if (r["case"], r["phase"], r["revision"]) == (case, "frontend", name)}
                if len(hashes) != 1:
                    raise RuntimeError(f"nondeterministic frontend IR: {case} {name}")
        for case in ("exact-class", "hierarchy-no-read"):
            hashes = {r["ir"]["sha256"] for r in doc["samples"] if r["case"] == case and r["phase"] == "frontend"}
            if len(hashes) != 1:
                raise RuntimeError(f"unchanged-path control IR differs: {case}")
        doc["control_ir_identical"] = True
        doc["frontend_ir_deterministic"] = True
        doc["medians"] = []
        for case in paths:
            for phase in ("frontend", "build"):
                for name in roots:
                    rows = [r for r in doc["samples"] if (r["case"], r["phase"], r["revision"]) == (case, phase, name)]
                    if rows:
                        doc["medians"].append({"case": case, "phase": phase, "revision": name,
                                               "wall_s": statistics.median(r["wall_s"] for r in rows),
                                               "min_s": min(r["wall_s"] for r in rows), "max_s": max(r["wall_s"] for r in rows)})
        doc["revisions_after"] = {name: revision(root) for name, root in roots.items()}
        for name, root in roots.items():
            if doc["revisions_after"][name]["compiler_source_sha256"] != doc["revisions"][name]["compiler_source_sha256"]:
                raise RuntimeError(f"compiler source changed during measurements: {name}")
            if not args.hosted:
                after = sha(root / "pystachy")
                doc["revisions_after"][name]["executable_sha256"] = after
                if after != doc["revisions"][name]["executable_sha256"]:
                    raise RuntimeError(f"compiler executable changed during measurements: {name}")
        if any(sha(path) != doc["inputs"][case]["sha256"] for case, path in paths.items()):
            raise RuntimeError("benchmark input changed during measurements")
        doc["sources_executables_inputs_unchanged"] = True
        doc["complete"] = True
        save()
    except BaseException as error:
        doc["error"] = repr(error)
        save()
        raise



if __name__ == "__main__":
    main()
