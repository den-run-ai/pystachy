"""Temporary ARM diagnostic: preserve the original probe and every failed run.

This is not a release gate or a runtime fix. Source inputs must match the failed
main commit; the hosted runtime IR must match both retained ARM bootstraps.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


BASE = "8434a911bed2064f50539806d9c05c57003241c3"
RUNTIME_IR_SHA256 = "cd645bebc4fea57b4824b5393843fea99bb31880a31a79dd825e1f34c388f830"
ASSERTION = '  if (gc_live >= 1048576) bad("cleared list storage survives collection");'
ROOT_SCAN = "  scan((const W *)((uintptr_t)__builtin_frame_address(0) & ~(uintptr_t)7), (const W *)gc_bottom);"
SCAN_DECLARATION = '__attribute__((noinline, no_sanitize("address"))) static void scan(const W *p, const W *e) {'
FIRST_MARK = "    s->mark[i >> 6] |= 1ULL << (i & 63); s->nmark++;"
MARK_ROOTS = "  mark_roots();"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"expected exactly one diagnostic anchor: {old}")
    return source.replace(old, new, 1)


def instrument(runtime: str, probe: str) -> tuple[str, str]:
    runtime = replace_once(runtime, SCAN_DECLARATION,
                           '#include "arm_listprobe_trace.h"\n' + SCAN_DECLARATION)
    runtime = replace_once(runtime, FIRST_MARK,
                           "    arm_diag_record(s, i, p, w);\n" + FIRST_MARK)
    runtime = replace_once(runtime, ROOT_SCAN,
                           "  arm_diag_stack_begin = ~((uintptr_t)__builtin_frame_address(0) & ~(uintptr_t)7);\n"
                           "  arm_diag_stack_end = ~(uintptr_t)gc_bottom;\n" + ROOT_SCAN)
    runtime = replace_once(runtime, MARK_ROOTS,
                           "  arm_diag_count = arm_diag_overflow = 0; arm_diag_in_roots = 1;\n"
                           + MARK_ROOTS + "\n  arm_diag_in_roots = 0;")
    probe = replace_once(probe, ASSERTION,
                         '  if (gc_live >= 1048576) { arm_diag_dump(buffers); bad("cleared list storage survives collection"); }')
    return runtime, probe


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("PYSTACHY_")}
    environment["PYSTACHY_LLVM"] = os.environ.get("PYSTACHY_LLVM", "/usr/lib/llvm-18/bin")
    environment["PYSTACHY_JOBS"] = "2"
    return environment


def run(command: list[str], log: Path, environment: dict[str, str],
        deadline: float, timeout: int) -> dict[str, object]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("diagnostic's 600-second command budget exhausted")
    started = time.monotonic()
    timed_out = False
    with log.open("wb") as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                    env=environment, timeout=min(timeout, remaining), check=False)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = None
    return {"command": command, "log": str(log), "returncode": returncode,
            "timed_out": timed_out, "seconds": round(time.monotonic() - started, 6)}


def require_build(command: list[str], log: Path, environment: dict[str, str],
                  deadline: float, report: dict) -> None:
    result = run(command, log, environment, deadline, 120)
    report["build"].append(result)
    if result["returncode"] != 0:
        raise RuntimeError(f"build failed; retained {log}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=24, choices=range(1, 25))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    output = root / "build/arm-listprobe-diagnostic"
    output.mkdir(parents=True, exist_ok=False)
    report = {"base": BASE, "status": "incomplete", "build": [], "runs": [],
              "requested_runs": 4 * args.repetitions, "platform": platform.platform(),
              "machine": platform.machine(), "python": sys.version,
              "run_id": os.environ.get("GITHUB_RUN_ID"),
              "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
              "sha": os.environ.get("GITHUB_SHA"), "repetitions": args.repetitions,
              "ignored_environment": sorted(key for key in os.environ
                                             if key.startswith("PYSTACHY_")
                                             and key not in {"PYSTACHY_LLVM", "PYSTACHY_JOBS"})}
    environment = clean_environment()
    deadline = time.monotonic() + 600
    try:
        if platform.machine() != "aarch64":
            raise RuntimeError("this diagnostic requires the native ARM runner")
        if Path(sys.executable).name == "pystachy":
            raise RuntimeError("use the pinned hosted CPython compiler")
        require_build(["git", "diff", "--exit-code", BASE, "--", ".",
                       ":(exclude).github/workflows/arm-listprobe-diagnostic.yml",
                       ":(exclude)tools/arm_listprobe_diagnostic.py",
                       ":(exclude)tools/arm_listprobe_trace.h",
                       ":(exclude)tools/test_arm_listprobe_diagnostic.py"],
                      output / "source-identity.log", environment, deadline, report)
        require_build(["git", "rev-parse", "HEAD"], output / "commit.log",
                      environment, deadline, report)
        require_build([str(Path(environment["PYSTACHY_LLVM"]) / "clang"), "--version"],
                      output / "clang-version.log", environment, deadline, report)
        require_build(["getconf", "PAGESIZE"], output / "page-size.log",
                      environment, deadline, report)
        require_build(["getconf", "GNU_LIBC_VERSION"], output / "libc-version.log",
                      environment, deadline, report)
        shutil.copyfile("/proc/cpuinfo", output / "cpuinfo.txt")
        require_build([sys.executable, "pystachy.py", "rt", "runtime.py", "-o", str(output / "rt1.ll")],
                      output / "hosted-runtime.log", environment, deadline, report)
        report["runtime_ir_sha256"] = digest(output / "rt1.ll")
        if report["runtime_ir_sha256"] != RUNTIME_IR_SHA256:
            raise RuntimeError("hosted runtime IR differs from the retained ARM bootstraps")
        runtime = (root / "runtime.c").read_text()
        probe = (root / "tools/listprobe.c").read_text()
        traced_runtime, traced_probe = instrument(runtime, probe)
        for variant in ("original", "instrumented"):
            directory = output / variant
            (directory / "tools").mkdir(parents=True)
            (directory / "runtime.c").write_text(runtime if variant == "original" else traced_runtime)
            (directory / "tools/listprobe.c").write_text(probe if variant == "original" else traced_probe)
            if variant == "instrumented":
                shutil.copyfile(root / "tools/arm_listprobe_trace.h", directory / "arm_listprobe_trace.h")
            clang = str(Path(environment["PYSTACHY_LLVM"]) / "clang")
            linker = str(Path(environment["PYSTACHY_LLVM"]) / "llvm-link")
            disassembler = str(Path(environment["PYSTACHY_LLVM"]) / "llvm-dis")
            source = "tools/listprobe.c" if variant == "original" else str(directory / "tools/listprobe.c")
            includes = [] if variant == "original" else ["-I", str(root)]
            commands = [
                [clang, "-O2", "-S", "-emit-llvm", *includes, source, "-o", str(directory / "listprobe.ll")],
                [linker, str(output / "rt1.ll"), str(directory / "listprobe.ll"), "-o", str(directory / "listprobe.bc")],
                [disassembler, str(directory / "listprobe.bc"), "-o", str(directory / "linked.ll")],
                [clang, "-O2", str(directory / "listprobe.bc"), "-o", str(directory / "listprobe"), "-lm"],
                [clang, "-O2", "-S", str(directory / "listprobe.bc"), "-o", str(directory / "listprobe.s")],
            ]
            for index, command in enumerate(commands):
                require_build(command, directory / f"build-{index}.log", environment, deadline, report)
        for variant in ("original", "instrumented"):
            directory = output / variant
            for iteration in range(args.repetitions):
                for mode in ("normal", "stress"):
                    probe_environment = environment.copy()
                    if mode == "stress":
                        probe_environment["PYSTACHY_GC_STRESS"] = "1"
                    log = directory / f"{iteration:02d}-{mode}.log"
                    result = run([str(directory / "listprobe")], log, probe_environment, deadline, 20)
                    result.update(variant=variant, iteration=iteration, mode=mode)
                    report["runs"].append(result)
                    print(json.dumps(result), flush=True)
        failures = [result for result in report["runs"] if result["returncode"] != 0]
        report["status"] = "reproduced_failure" if failures else "no_failure_observed"
        report["failed_runs"] = len(failures)
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        report["error"] = str(error)
        print(f"diagnostic error: {error}", file=sys.stderr, flush=True)
    finally:
        report["files"] = {str(path.relative_to(output)): digest(path)
                           for path in sorted(output.rglob("*")) if path.is_file()}
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"status": report["status"], "runs": len(report["runs"]),
                          "failed_runs": report.get("failed_runs"),
                          "error": report.get("error")}), flush=True)
    return 0 if report["status"] == "no_failure_observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

