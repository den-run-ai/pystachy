"""Check then time CPython and two prebuilt native compilers' AOT workloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CASES = [f"{kind}_{rate}" for kind in ("dict", "list") for rate in ("hit", "miss", "mixed")]
CASES += ["word_count", "index_miss", "int_miss"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output(command, **kwargs):
    result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=180, **kwargs)
    if result.stderr:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def identity(root):
    names = output(["git", "ls-files", "pystachy.py", "runtime.c", "runtime.py", "src", "lib", "mpz", "ryu"], cwd=root).splitlines()
    sources = {name: sha(root / name) for name in names}
    return {"commit": output(["git", "rev-parse", "HEAD"], cwd=root),
            "status": output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root),
            "root": str(root), "sources": sources, "compiler_sha256": sha(root / "pystachy")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=ROOT)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument("--hit-multiplier", type=int, default=100)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.samples < 1 or args.hit_multiplier < 1:
        parser.error("repeats, samples and hit-multiplier must be positive")
    os.sched_setaffinity(0, {args.cpu})
    roots = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    work = args.output.resolve().parent
    work.mkdir(parents=True, exist_ok=True)
    source = ROOT / "bench/local_exceptions/workload.py"
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env.update(PYSTACHY_LLVM=str(args.llvm.resolve()), PYSTACHY_AOT_OPT="2", PYTHONHASHSEED="0")
    report = {"complete": False, "platform": platform.platform(), "cpu": args.cpu,
              "cpuinfo": Path("/proc/cpuinfo").read_text().split("\n\n")[0],
              "python": output([args.python, "--version"]),
              "llvm": output([str(args.llvm / "clang"), "--version"]),
              "environment": {key: value for key, value in env.items() if key.startswith("PYSTACHY_")},
              "source_sha256": sha(source), "runner_sha256": sha(Path(__file__)),
              "load_before": os.getloadavg(), "repeats": args.repeats, "batch_size": 512,
              "hit_multiplier": args.hit_multiplier,
              "scope": "in-process workload time; excludes startup, input creation and AOT build; includes containers and GC",
              "variants": {}, "samples": [], "medians_s": {}}
    try:
        commands = {"cpython": [args.python, str(source)]}
        for name, root in roots.items():
            report["variants"][name] = identity(root)
            binary = work / (name + "-workload")
            binary.unlink(missing_ok=True)
            command = [str(root / "pystachy"), "build", str(source), "-o", str(binary)]
            result = subprocess.run(command, cwd=root, env=dict(env, PYSTACHY_HOME=str(root)),
                                    capture_output=True, text=True, timeout=180, check=True)
            report["variants"][name].update(build_command=command, build_stdout=result.stdout,
                                           build_stderr=result.stderr, executable_sha256=sha(binary))
            commands[name] = [str(binary)]
        for case in CASES:
            repeats = args.repeats * (args.hit_multiplier if case.endswith("_hit") else 1)
            expected = int(output(commands["cpython"] + [case, "1"], env=env).splitlines()[0])
            for command in commands.values():
                if int(output(command + [case, "1"], env=env).splitlines()[0]) != expected:
                    raise RuntimeError(f"pre-timing checksum mismatch: {case}")
            names = list(commands)
            for sample in range(args.samples):
                order = names[sample % 3:] + names[:sample % 3]
                for name in order:
                    checksum, seconds = output(commands[name] + [case, str(repeats)], env=env).splitlines()
                    if int(checksum) != expected * repeats:
                        raise RuntimeError(f"timed checksum mismatch: {case}/{name}")
                    report["samples"].append(dict(case=case, variant=name, sample=sample,
                                                  repeats=repeats, checksum=int(checksum), seconds=float(seconds)))
            medians = {name: statistics.median(row["seconds"] for row in report["samples"]
                       if row["case"] == case and row["variant"] == name) for name in names}
            report["medians_s"][case] = medians
            print(case, json.dumps(medians), flush=True)
        for name, root in roots.items():
            for key, value in identity(root).items():
                if report["variants"][name][key] != value:
                    raise RuntimeError(f"compiler input changed during measurement: {name}/{key}")
        report["complete"] = True
    except BaseException as error:
        report["error"] = repr(error)
        raise
    finally:
        report["load_after"] = os.getloadavg()
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
