"""Interleaved, fresh-process frontend measurements for exception-binding scope scans.

Both checkouts compile the same generated files. Every timed/observed IR result,
diagnostic and status must match. Counting runs are separate from timing runs;
compiler preparation and LLVM native-code generation are excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed(root, source, output):
    """Count actual whole-function scans and index visits, without compiler changes."""
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("binding_compiler", root / "pystachy.py")
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    from src.pystachy_compiler import analysis, exceptions

    scan = analysis.binds_other.__code__
    statement = analysis.stmt_binds.__code__
    index = getattr(analysis, "other_bindings", None)
    index = index.__code__ if index else None
    bind = exceptions.gen_bind_as.__code__
    counts = dict(handler_bindings=0, scan_statements=0, index_statements=0, indexes=0)
    scan_depth = index_depth = 0

    def profile(frame, event, arg):
        nonlocal scan_depth, index_depth
        code = frame.f_code
        if code is scan:
            if event == "call":
                scan_depth += 1
            elif event == "return":
                scan_depth -= 1
        elif code is index:
            if event == "call":
                counts["indexes"] += index_depth == 0
                counts["index_statements"] += len(frame.f_locals["body"])
                index_depth += 1
            elif event == "return":
                index_depth -= 1
        elif event == "call":
            if code is statement and scan_depth:
                counts["scan_statements"] += 1
            elif code is bind:
                counts["handler_bindings"] += 1

    sys.argv = [str(root / "pystachy.py"), "ir", str(source), "-o", str(output)]
    sys.setprofile(profile)
    try:
        compiler.main()
    finally:
        sys.setprofile(None)
    print(json.dumps(counts, sort_keys=True))


def execute(command, cwd, env):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    try:
        process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=180)
        returncode, stdout, stderr, timed_out = process.returncode, process.stdout, process.stderr, False
    except subprocess.TimeoutExpired as error:
        # run() kills and waits for this direct frontend process before returning.
        # Preserve the failed observation; the caller records it before rejecting it.
        returncode, stdout, stderr, timed_out = None, error.stdout or b"", error.stderr or b"", True
    wall = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(command=[str(v) for v in command], returncode=returncode, timed_out=timed_out, timeout_s=180,
                stdout=stdout.decode("utf-8", "backslashreplace"),
                stderr=stderr.decode("utf-8", "backslashreplace"),
                wall_s=wall, cpu_s=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime)


def identity(root, native):
    files = [root / "pystachy.py", *sorted((root / "src").rglob("*.py")), *sorted((root / "lib").rglob("*.py"))]
    sources = {str(p.relative_to(root)): sha(p) for p in files}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root, text=True)
    return dict(root=str(root), commit=commit, status=status.splitlines(), sources=sources,
                source_sha256=hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
                native={"path": str(native), "sha256": sha(native)} if native else None)


def main():
    if sys.argv[1:2] == ["--observe"]:
        observed(*(Path(value).resolve() for value in sys.argv[2:]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=ROOT)
    parser.add_argument("--baseline-native", type=Path)
    parser.add_argument("--candidate-native", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--sizes", default="256,512,1024")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--counts", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sizes = [int(value) for value in args.sizes.split(",")]
    if min(sizes) < 1 or args.rounds < 1 or bool(args.baseline_native) != bool(args.candidate_native):
        parser.error("positive sizes/rounds and both native compilers (or neither) are required")
    if args.cpu is not None:
        if not hasattr(os, "sched_setaffinity"):
            parser.error("--cpu requires process affinity support")
        os.sched_setaffinity(0, {args.cpu})
    roots = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    natives = {"baseline": args.baseline_native, "candidate": args.candidate_native}
    natives = {name: path.resolve() if path else None for name, path in natives.items()}
    variants = {name: identity(root, natives[name]) for name, root in roots.items()}
    sys.path.insert(0, str(ROOT))
    from tools.scaling import funcs, handlers, samehandlers, write

    report = dict(complete=False, python={"harness": sys.version, "command": args.python,
                                         "compiler": subprocess.check_output([args.python, "--version"], text=True).strip()},
                  platform=platform.platform(),
                  affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                  load_before=list(os.getloadavg()), harness_sha256=sha(__file__),
                  generator_sha256=sha(ROOT / "tools/scaling.py"), variants=variants, cases=[],
                  scope="frontend, startup and LLVM IR writing; excludes compiler preparation and LLVM backend",
                  memory_note="RSS is not measured by this timing runner")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    environment["PYTHONHASHSEED"] = "0"
    try:
        with tempfile.TemporaryDirectory(prefix="pystachy-exception-bindings-") as directory:
            for shape, generator in (("handlers", handlers), ("samehandlers", samehandlers), ("nohandlers", funcs)):
                for size in sizes:
                    source = Path(write(str(Path(directory) / f"{shape}-{size}"), generator(size)))
                    case = dict(shape=shape, size=size, source_sha256=sha(source), samples=[], counts={})
                    report["cases"].append(case)
                    oracle = execute([args.python, str(source)], ROOT, environment)
                    case["cpython"] = oracle
                    expected_stdout = f"{size + 20}\n" if shape == "nohandlers" else "1\n"
                    if (oracle["returncode"], oracle["stdout"], oracle["stderr"]) != (0, expected_stdout, ""):
                        raise RuntimeError("generated program failed its independent CPython oracle")
                    expected = None
                    modes = ["hosted", "native"] if args.baseline_native else ["hosted"]
                    for mode in modes:
                        for repeat in range(args.rounds):
                            order = ("baseline", "candidate") if repeat % 2 == 0 else ("candidate", "baseline")
                            for variant in order:
                                root = roots[variant]
                                output = source.parent / "out.ll"
                                output.unlink(missing_ok=True)
                                producer = [args.python, str(root / "pystachy.py")] if mode == "hosted" else [str(natives[variant])]
                                sample = execute(producer + ["ir", str(source), "-o", str(output)], root,
                                                 dict(environment, PYSTACHY_HOME=str(root)))
                                sample.update(variant=variant, mode=mode, repeat=repeat,
                                              ir_sha256=sha(output) if output.is_file() else None)
                                case["samples"].append(sample)
                                witness = (sample["returncode"], sample["stdout"], sample["stderr"], sample["ir_sha256"])
                                if sample["returncode"] != 0 or sample["ir_sha256"] is None or output.stat().st_size == 0:
                                    raise RuntimeError(f"frontend failed: {sample}")
                                if expected is not None and witness != expected:
                                    raise RuntimeError(f"frontend witnesses differ for {shape} {size}")
                                expected = witness
                    if args.counts:
                        for variant, root in roots.items():
                            output = source.parent / "observed.ll"
                            output.unlink(missing_ok=True)
                            sample = execute([args.python, str(Path(__file__).resolve()), "--observe", str(root), str(source), str(output)],
                                             root, dict(environment, PYSTACHY_HOME=str(root)))
                            case["counts"][variant] = sample
                            if sample["returncode"] != 0 or sample["stderr"] or not output.is_file() or sha(output) != expected[3]:
                                raise RuntimeError(f"counted run differs: {sample}")
                            sample["operations"] = json.loads(sample["stdout"])
                    case["medians"] = {f"{mode}-{variant}": statistics.median(s["wall_s"] for s in case["samples"]
                                           if s["mode"] == mode and s["variant"] == variant)
                                       for mode in modes for variant in roots}
                    print(shape, size, json.dumps(case["medians"], sort_keys=True), flush=True)
        for variant, root in roots.items():
            after = identity(root, natives[variant])
            if (after["source_sha256"], after["native"]) != (variants[variant]["source_sha256"], variants[variant]["native"]):
                raise RuntimeError("compiler inputs changed during the experiment")
        report["complete"] = True
    except BaseException as error:
        report["error"] = repr(error)
        raise
    finally:
        report["load_after"] = list(os.getloadavg())
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
