"""Which unannotated pyperformance benchmarks compile, and what recorded types change.

usage: python3 -m pip download pyperformance==1.14.0 --no-deps -d build/pyperf
       python3 tools/pyperformance_compile_census.py --wheel build/pyperf/pyperformance-1.14.0-py3-none-any.whl
           [--compiler ./pystachy] [--output docs/benchmarks/pyperformance-compile-census.json]

The benchmark sources are read from the pinned wheel without installing or importing it. Each
benchmark's pyperf harness (the `if __name__ == "__main__":` block) is replaced by one direct call
of its benchmark function, with `time.perf_counter` for `pyperf.perf_counter`; the benchmark code
is unchanged. Stages, each compiled with `pystachy build`:

- original: the unannotated source;
- traced: tools/trace_annotate.py records the types of one CPython run and adds the missing
  annotations (skipped when the original stops at an unsupported module, which no type fixes);
- edited: for Richards, one labeled source edit whose CPython output is checked to be unchanged,
  then traced again.

Each stage records the first compile error, a coarse kind (module, types or language) and, for
traced stages, the positions whose observations did not join, with their sample counts. A
feature probe records whether isinstance() narrows a base-typed value to a subclass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
WHEEL_SHA256 = "94068ac2935b6952ccb5e8a302eb9cebc26e82454494bef6e53822738adf0049"  # PyPI pyperformance 1.14.0
DRIVERS = {
    "richards": "print(Richards().run(1))\n",
    "deltablue": "delta_blue(100)\nprint('deltablue done')\n",
    "raytrace": "bench_raytrace(1, DEFAULT_WIDTH, DEFAULT_HEIGHT, None)\nprint('raytrace done')\n",
    "chaos": "main()\nprint('chaos done')\n",
    "go": "print(versus_cpu())\n",
    "float": "print(benchmark(POINTS))\n",
}
EDITS = {
    "richards": [
        ("BUFSIZE_RANGE = range(BUFSIZE)", "BUFSIZE_RANGE = list(range(BUFSIZE))",
         "a range object kept in a global; it is only iterated"),
    ],
}


def strip_harness(name, source):
    """The benchmark with its pyperf harness replaced by a direct call."""
    head, marker, _ = source.partition('\nif __name__ == "__main__":')
    if not marker or "import pyperf\n" not in head:
        raise RuntimeError(f"{name}: no pyperf harness found")
    head = head.replace("import pyperf\n", "import time\n").replace("pyperf.perf_counter()", "time.perf_counter()")
    if name == "chaos":  # main(runner, args) builds the splines, then calls the runner
        head = re.sub(r"\n    runner\.metadata\[[^\n]*", "", head)
        head = head.replace("def main(runner, args):", "def main():")
        head = head.replace("Chaosgame(splines, args.thickness)", "Chaosgame(splines, DEFAULT_THICKNESS)")
        head = re.sub(r"runner\.bench_func\('chaos', chaos\.create_image_chaos,\s*args\.width, args\.height, args\.iterations,"
                      r"\s*args\.filename, args\.rng_seed\)",
                      "chaos.create_image_chaos(DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_ITERATIONS, None, DEFAULT_RNG_SEED)", head)
        if "args." in head.split("def main():")[1].split("\n\n\n")[0]:
            raise RuntimeError("chaos: harness arguments left in main()")
    head = re.sub(r"\n\ndef add_cmdline_args\(cmd, args\):.*", "\n", head, flags=re.S)
    if "runner." in head or "pyperf" in head:
        raise RuntimeError(f"{name}: harness code left after stripping")
    return head.rstrip() + "\n\n\n" + DRIVERS[name]


def run(command, timeout=1800):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def first_error(text, directory):
    for line in text.splitlines():
        if "error:" in line:
            return line.replace(str(directory) + "/", "").strip()
    return text.strip().splitlines()[-1] if text.strip() else ""


def kind(error):
    if re.search(r"module '[\w.]+' is not supported", error):
        return "module"
    if re.search(r"annotate|cannot infer|must return|None is only supported|expected \w+, got", error):
        return "types"
    return "language"


def compile_stage(compiler, program, directory):
    result = run([*compiler, "build", str(program), "-o", str(program.with_suffix(""))])
    if result.returncode == 0:
        return {"compiles": True}
    error = first_error(result.stdout + result.stderr, directory)
    return {"compiles": False, "first_error": error, "kind": kind(error)}


def traced_stage(compiler, program, directory, label):
    annotated = directory / f"{label}.py"
    report = directory / f"{label}.json"
    result = run([sys.executable, "-I", str(ROOT / "tools/trace_annotate.py"), str(program), "-o", str(annotated),
                  "--report", str(report)])
    if result.returncode != 0:
        raise RuntimeError(f"{label}: tracing failed\n{result.stderr}")
    data = json.loads(report.read_text(encoding="utf-8"))
    stage = {"annotations_added": data["annotations_added"], "unannotated": data["unannotated"]}
    check = run([sys.executable, "-I", str(annotated)])
    stage["annotated_runs_on_cpython"] = check.returncode == 0
    stage.update(compile_stage(compiler, annotated, directory))
    return stage


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--wheel", type=Path, required=True, help="pyperformance-1.14.0-py3-none-any.whl")
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--benchmarks", default=",".join(DRIVERS))
    parser.add_argument("--output", type=Path, default=ROOT / "build/pyperformance-census/results.json")
    args = parser.parse_args()
    wheel_hash = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    if wheel_hash != WHEEL_SHA256:
        parser.error(f"{args.wheel} is not the pinned pyperformance 1.14.0 wheel (sha256 {wheel_hash})")
    compiler = shlex.split(args.compiler)
    directory = ROOT / "build/pyperformance-census"
    directory.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(ROOT)]
    info = {"schema": "pystachy-pyperformance-compile-census-v1", "platform": platform.platform(), "python": sys.version,
            "compiler": compiler, "git_head": run([*git, "rev-parse", "HEAD"]).stdout.strip(),
            "git_status": run([*git, "status", "--short"]).stdout, "wheel_sha256": wheel_hash, "benchmarks": {}}
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    if llvm:
        info["llvm"] = run([str(Path(llvm) / "clang"), "--version"]).stdout.splitlines()[0]
    with zipfile.ZipFile(args.wheel) as wheel:
        sources = {name: wheel.read(f"pyperformance/data-files/benchmarks/bm_{name}/run_benchmark.py").decode("utf-8")
                   for name in args.benchmarks.split(",")}
    for name, source in sources.items():
        stripped = directory / f"{name}.py"
        stripped.write_text(strip_harness(name, source), encoding="utf-8")
        oracle = run([sys.executable, "-I", str(stripped)])
        if oracle.returncode != 0:
            raise RuntimeError(f"{name}: the stripped benchmark fails on CPython\n{oracle.stderr}")
        row = {"source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(), "cpython_output": oracle.stdout,
               "original": compile_stage(compiler, stripped, directory)}
        if not row["original"]["compiles"] and row["original"]["kind"] != "module":
            row["traced"] = traced_stage(compiler, stripped, directory, f"{name}_traced")
        if name in EDITS:
            text = stripped.read_text(encoding="utf-8")
            for old, new, _ in EDITS[name]:
                if text.count(old) != 1:
                    raise RuntimeError(f"{name}: edit {old!r} does not apply exactly once")
                text = text.replace(old, new)
            edited = directory / f"{name}_edited.py"
            edited.write_text(text, encoding="utf-8")
            same = run([sys.executable, "-I", str(edited)])
            if same.stdout != oracle.stdout:
                raise RuntimeError(f"{name}: the edits change CPython's output")
            row["edited"] = {"edits": [{"from": o, "to": n, "why": w} for o, n, w in EDITS[name]],
                             **traced_stage(compiler, edited, directory, f"{name}_edited_traced")}
        info["benchmarks"][name] = row
    probe = ROOT / "tools/fixtures/isinstance_narrowing.py"
    copy = directory / "isinstance_narrowing.py"
    copy.write_text(probe.read_text(encoding="utf-8"), encoding="utf-8")
    info["isinstance_narrowing_probe"] = compile_stage(compiler, copy, directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print("| Benchmark | Stage | Result |\n| --- | --- | --- |")
    for name, row in info["benchmarks"].items():
        for stage in ("original", "traced", "edited"):
            if stage in row:
                s = row[stage]
                extra = f" ({s['annotations_added']} annotations added)" if "annotations_added" in s else ""
                result = "compiles" if s["compiles"] else f"{s['kind']}: `{s['first_error']}`"
                print(f"| {name} | {stage} | {result}{extra} |")
    probe_result = info["isinstance_narrowing_probe"]
    print(f"isinstance narrowing probe: {'compiles' if probe_result['compiles'] else probe_result['first_error']}")


if __name__ == "__main__":
    main()
