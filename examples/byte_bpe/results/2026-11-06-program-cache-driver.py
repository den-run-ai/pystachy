"""Optional, isolated byte-BPE launch check for the published #1103 prototype.

Run only when a timing window is free. This script does not build or edit the
historical compiler. Its private Probe cache and LLVM wrappers are temporary.
The published stage benchmark remains independent of this unmerged cache.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import statistics
import subprocess
import sys
import tempfile
import time


SCRATCH = Path(__file__).resolve().parent
HISTORICAL = Path("/workspace/scratch/e98dc1e3e6cd/pystachy")
EXPECTED_COMMIT = "706b47facf690f83c234097706e8fef9230c1cad"
EXPECTED_COMPILER = "df000379236b3b920463c1c1960e4a73bef5672aeefb46bb580664b944d3643b"
CORPUS_SHA256 = "6607193e67b7b459d082f5f2aea724e470615643d63ad2e205123b3076223da4"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(command: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True,
                          text=True, timeout=30).stdout.strip()


def atomic_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def distribution(values: list[float]) -> dict:
    return {"median": statistics.median(values), "min": min(values), "max": max(values),
            "samples": values}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=SCRATCH / "pystachy")
    parser.add_argument("--source", type=Path,
                        help="deterministic demo; defaults to demo.py, byte_bpe.py or tokenize.py")
    parser.add_argument("--home", type=Path, default=HISTORICAL)
    parser.add_argument("--compiler", type=Path, default=HISTORICAL / "pystachy")
    parser.add_argument("--expected-compiler-sha256", default=EXPECTED_COMPILER)
    parser.add_argument("--llvm", type=Path,
                        default=HISTORICAL.parent / "toolchains/ubuntu-18.1.3-1ubuntu1-amd64/bin")
    parser.add_argument("--python", default=str(HISTORICAL.parent / "dev/bin/python") + " -B")
    parser.add_argument("--cpu", type=int, default=0)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--text", default="Hello, Sebastian! 日本語 🦉 Æ É Ġ\t\n")
    parser.add_argument("--output", type=Path, default=SCRATCH / "byte-bpe-cache.json")
    args = parser.parse_args()
    if sys.platform != "linux" or not hasattr(os, "sched_getaffinity"):
        parser.error("the published native cache prototype requires Linux")
    if args.rounds < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("rounds must be positive and timeout must be positive and finite")
    if args.cpu not in os.sched_getaffinity(0):
        parser.error("--cpu must select an allowed CPU")
    os.sched_setaffinity(0, {args.cpu})
    args.project, args.home = args.project.resolve(), args.home.resolve()
    args.compiler, args.llvm = args.compiler.resolve(), args.llvm.resolve()
    bench = args.project / "bench/pyperformance"
    corpus = bench / "data/frankenstein_intro.txt"
    if args.source is None:
        candidates = [args.project / "examples/byte_bpe" / name
                      for name in ("demo.py", "byte_bpe.py", "tokenize.py")]
        args.source = next((path for path in candidates if path.is_file()), candidates[0])
    source = args.source.resolve()
    arguments = [str(corpus), "1024", args.text]
    report = {"schema": "pystachy-byte-bpe-program-cache-v1", "status": "running",
              "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "cache_commit": EXPECTED_COMMIT, "source": str(source), "arguments": arguments,
              "rounds": args.rounds, "cpu_affinity": sorted(os.sched_getaffinity(0)),
              "platform": platform.platform(), "load_average_start": os.getloadavg(),
              "controller_python": sys.version, "runs": [], "pairs": [],
              "rss_note": "The verified Probe helper records wall time, not per-child RSS; RSS was not measured.",
              "scopes": {
                  "first_use_fill": "Runtime artifacts warm; program artifacts/static hashes initially absent.",
                  "cache_hit": "Fresh process reusing validated native code; all training and tokenization execute again.",
                  "uncached": "PYSTACHY_PROGRAM_CACHE=0 with the same compiler and warm runtime artifacts.",
                  "correctness": "Complete demo stdout, ordinary stderr and status versus CPython on every run.",
                  "limits": "This checks opt-in #1103, not the concurrently developed default-cache changes; no AOT comparison."}}
    atomic_report(args.output, report)
    p = None
    try:
        head = command_output(["git", "rev-parse", "HEAD"], args.home)
        if head != EXPECTED_COMMIT:
            raise ValueError(f"cache checkout moved: {head}")
        compiler_hash = digest(args.compiler)
        if compiler_hash != args.expected_compiler_sha256:
            raise ValueError("compiler binary does not match the selected verified SHA-256")
        if digest(corpus) != CORPUS_SHA256:
            raise ValueError("full Frankenstein corpus SHA-256 mismatch")
        inputs = {Path(__file__).resolve(), source, corpus, bench / "bpe_tokeniser.py", args.compiler,
                  args.home / "pystachy.py", args.home / "runtime.c", args.home / "runtime.py",
                  args.home / "tools/program_cache_probe.py", args.home / "tools/jitprobe.py"}
        for subtree in ("src", "lib", "mpz", "ryu"):
            inputs.update(path for path in (args.home / subtree).rglob("*")
                          if path.is_file() and path.suffix in (".py", ".c", ".h"))
        input_hashes = {str(path): digest(path) for path in sorted(inputs)}
        report.update(compiler_sha256=compiler_hash, input_sha256=input_hashes,
                      cache_git_status=command_output(["git", "status", "--porcelain"], args.home),
                      project_git_revision=command_output(["git", "rev-parse", "HEAD"], args.project),
                      project_git_status=command_output(["git", "status", "--porcelain"], args.project),
                      oracle_python=command_output(shlex.split(args.python) + ["--version"]),
                      corpus_bytes=corpus.stat().st_size,
                      llvm_version=command_output([str(args.llvm / "clang"), "--version"]))
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(args.home / "tools"))
        from program_cache_probe import Probe
        probe_args = argparse.Namespace(home=str(args.home), compiler=str(args.compiler),
                                        python=args.python, llvm=str(args.llvm), timeout=args.timeout)
        with tempfile.TemporaryDirectory(prefix="byte-bpe-cache-", dir=SCRATCH) as temporary:
            p = Probe(probe_args, Path(temporary))
            # Probe.oracle uses Probe.launch and therefore this same environment.
            p.env.pop("PYTHONHOME", None)
            p.env.update(PYSTACHY_PATH=str(bench), PYTHONPATH=str(bench),
                         PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
            report["llvm_tools"] = p.real
            report["declared_toolchain_inputs"] = p.env["PYSTACHY_PROGRAM_CACHE_INPUTS"].split(":")
            report["environment"] = {key: value for key, value in p.env.items()
                                     if key.startswith("PYSTACHY_") or key.startswith("PYTHON")}
            try:
                expected = p.oracle(source, arguments, cwd=args.project)
                p.check(not expected.timed_out and expected.status == 0, "CPython oracle succeeds")
                p.check(expected.observable[2] == b"", "CPython demo has no stderr")
                p.check(b"Exact round trip: True\n" in expected.stdout, "CPython round trip succeeds")
                warm = p.run("runtime_warm", source, arguments, cwd=args.project,
                             changes={"PYSTACHY_PROGRAM_CACHE": "0"})
                p.matches(warm, expected, "runtime-warm uncached launch")
                p.check(bool(warm.tools) and "hit" not in warm.events,
                        "uncached warmup actually invokes LLVM")
                fill = p.run("first_use_fill", source, arguments, cwd=args.project)
                p.matches(fill, expected, "first use fill")
                p.miss(fill, "first use fill")
                p.check("stored" in fill.events, "first fill publishes executable")
                hit = p.run("initial_cache_hit", source, arguments, cwd=args.project)
                p.matches(hit, expected, "initial cached output")
                p.hit(hit, "initial BPE cache hit")
                report["first_use_fill_seconds"] = fill.seconds
                report["initial_hit_seconds"] = hit.seconds
                print("PASS first fill and hit: complete output; zero frontend/LLVM calls on hit", flush=True)
                for repeat in range(args.rounds):
                    modes = ("uncached", "cache_hit") if repeat % 2 == 0 else ("cache_hit", "uncached")
                    pair = {"round": repeat + 1, "order": list(modes)}
                    for mode in modes:
                        result = p.run(f"round-{repeat + 1}:{mode}", source, arguments, cwd=args.project,
                                       changes={"PYSTACHY_PROGRAM_CACHE": "0" if mode == "uncached" else "1"})
                        p.matches(result, expected, f"round {repeat + 1} {mode}")
                        if mode == "cache_hit":
                            p.hit(result, f"round {repeat + 1} cache hit")
                        else:
                            p.check(bool(result.tools) and "hit" not in result.events,
                                    f"round {repeat + 1} uncached launch actually invokes LLVM")
                        pair[mode + "_seconds"] = result.seconds
                    pair["speedup"] = pair["uncached_seconds"] / pair["cache_hit_seconds"]
                    report["pairs"].append(pair)
                    report.update(runs=p.runs, assertions=p.assertions)
                    atomic_report(args.output, report)
                    print(f"PASS pair {repeat + 1}/{args.rounds}: {pair['speedup']:.3f}x", flush=True)
                report["summary"] = {
                    "uncached_seconds": distribution([row["uncached_seconds"] for row in report["pairs"]]),
                    "cache_hit_seconds": distribution([row["cache_hit_seconds"] for row in report["pairs"]]),
                    "paired_speedup": distribution([row["speedup"] for row in report["pairs"]]),
                    "verified_hits_without_frontend_or_llvm": args.rounds + 1}
                report["cache_files"] = [
                    {"name": str(path.relative_to(p.cache)), "bytes": path.stat().st_size,
                     "sha256": digest(path)} for path in p.entry_files()]
            finally:
                report.update(runs=p.runs, assertions=p.assertions)
                atomic_report(args.output, report)
        for name, expected_hash in input_hashes.items():
            if digest(Path(name)) != expected_hash:
                raise ValueError(f"input changed during cache measurements: {name}")
        report.update(status="passed", input_hashes_unchanged=True, load_average_end=os.getloadavg())
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        if p is not None:
            report.update(runs=p.runs, assertions=p.assertions)
        atomic_report(args.output, report)
        raise
    atomic_report(args.output, report)
    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
