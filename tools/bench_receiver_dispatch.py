"""How much a receiver-class specialization could gain over Pystachy's base-typed method dispatch.

usage: python3 tools/bench_receiver_dispatch.py [--compiler ./pystachy] [--samples 7] [--rounds 200000]
           [--timing-cpu N] [--output docs/benchmarks/receiver-dispatch.json]

Builds tools/fixtures/receiver_skew.py as is (a `list[Constraint]` plan dispatching on each
receiver) and a concrete control derived from it, whose plan is `list[EqualityConstraint]`: only
the plan's annotations and construction change, which is asserted on the AST, so every method
body is the same. Outputs must match CPython's. The host IR of the generic `execute` is kept as
evidence of how the call compiles. Samples rotate the variant order and pin one CPU; each reports
the in-process loop time per constraint (stderr), excluding startup and plan construction.

The concrete control is an upper bound for a specialization guarded on the dominant class: the
monomorphic plan still pays dispatch with perfectly predictable branches, and the mixed plan
also executes the other classes' bodies.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tools/fixtures/receiver_skew.py"
CONSTRAINTS = 1000


def concrete_source(source):
    """The fixture with a list[EqualityConstraint] plan; classes and execute's body unchanged."""
    tree = ast.parse(source)
    before = {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.ClassDef)}
    body_before = [ast.dump(s) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute" for s in n.body]
    dominant = ast.parse("list[EqualityConstraint]", mode="eval").body
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "build":
            node.returns = dominant
            for st in ast.walk(node):
                if isinstance(st, ast.AnnAssign) and ast.unparse(st.target) == "plan":
                    st.annotation = dominant
                if isinstance(st, ast.For):
                    for i, inner in enumerate(st.body):
                        if isinstance(inner, ast.If):  # keep only the dominant class's branch
                            branch = inner
                            while branch.orelse and isinstance(branch.orelse[0], ast.If):
                                branch = branch.orelse[0]
                            st.body[i:i + 1] = branch.orelse
                            break
        if isinstance(node, ast.FunctionDef) and node.name == "execute":
            node.args.args[0].annotation = dominant
    after = {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.ClassDef)}
    body_after = [ast.dump(s) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute" for s in n.body]
    if before != after or body_before != body_after:
        raise RuntimeError("the concrete control changed a class or the execute loop")
    text = ast.unparse(tree) + "\n"
    if "ScaleConstraint(1" in text or "EditConstraint(2" in text:
        raise RuntimeError("the concrete control still constructs other constraint classes")
    return text


def run(command, env=None, cpu=None):
    pin = None if cpu is None else (lambda: os.sched_setaffinity(0, {cpu}))
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=600, preexec_fn=pin)
    if result.returncode != 0:
        raise RuntimeError(f"{shlex.join(command)} failed:\n{result.stdout}{result.stderr}")
    return result


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dispatch_evidence(ir):
    """The generic execute's receiver calls: class-tag compares and direct or indirect calls."""
    match = re.search(r"^define [^\n]*@f\.execute[^\n]*\{\n(.*?)^\}", ir, re.MULTILINE | re.DOTALL)
    if not match:
        raise RuntimeError("no generic execute in the host IR")
    body = match[1]
    return {"tag_compares": len(re.findall(r"icmp eq i64 %\w+, \d+", body)),
            "direct_method_calls": sorted(set(re.findall(r"call \w+ @(m\.[\w.]+)\(", body))),
            "indirect_calls": len(re.findall(r"call \w+ %\w+\(", body)),
            "ir": body}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--rounds", type=int, default=200000)
    parser.add_argument("--timing-cpu", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "build/receiver-dispatch/results.json")
    args = parser.parse_args()
    compiler = shlex.split(args.compiler)
    build = ROOT / "build/receiver-dispatch"
    build.mkdir(parents=True, exist_ok=True)
    generic_py = build / "receiver_generic.py"
    concrete_py = build / "receiver_concrete.py"
    source = FIXTURE.read_text(encoding="utf-8")
    generic_py.write_text(source, encoding="utf-8")
    concrete_py.write_text(concrete_source(source), encoding="utf-8")
    affinity = os.sched_getaffinity(0)
    cpu = min(affinity) if args.timing_cpu is None else args.timing_cpu
    if cpu not in affinity:
        parser.error("--timing-cpu is outside the allowed affinity set")
    info = {"schema": "pystachy-receiver-dispatch-v1", "platform": platform.platform(), "python": sys.version,
            "compiler": compiler, "git_head": run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).stdout.strip(),
            "git_status": run(["git", "-C", str(ROOT), "status", "--short"]).stdout,
            "constraints": CONSTRAINTS, "rounds": args.rounds, "samples": args.samples, "timing_cpu": cpu,
            "inputs": {p.name: sha256(p) for p in (FIXTURE, generic_py, concrete_py)}}
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    if llvm:
        info["llvm"] = run([str(Path(llvm) / "clang"), "--version"]).stdout.splitlines()[0]
    variants = [("base_mixed", build / "receiver_generic", "mixed"),
                ("base_mono", build / "receiver_generic", "mono"),
                ("concrete_mono", build / "receiver_concrete", "mono")]
    for py, exe in ((generic_py, build / "receiver_generic"), (concrete_py, build / "receiver_concrete")):
        run([*compiler, "build", str(py), "-o", str(exe)])
        info["inputs"][exe.name] = sha256(exe)
    checks = {}
    for name, exe, mode in variants:
        oracle = run([sys.executable, str(generic_py if name.startswith("base") else concrete_py), mode, "20"]).stdout
        native = run([str(exe), mode, "20"]).stdout
        if native != oracle:
            raise RuntimeError(f"{name}: {native!r} differs from CPython's {oracle!r}")
        checks[name] = native.strip()
    info["cpython_checks"] = checks
    ir = run([*compiler, "ir", str(generic_py)]).stdout
    info["generic_execute"] = dispatch_evidence(ir)
    samples = {name: [] for name, _, _ in variants}
    for sample in range(args.samples):
        offset = sample % len(variants)
        for name, exe, mode in variants[offset:] + variants[:offset]:
            result = run([str(exe), mode, str(args.rounds)], cpu=cpu)
            seconds = float(result.stderr.split()[1])
            samples[name].append(seconds / (args.rounds * CONSTRAINTS) * 1e9)
    info["ns_per_constraint"] = samples
    info["summary"] = {name: {"median": statistics.median(v), "min": min(v), "max": max(v)} for name, v in samples.items()}
    info["paired_ratios"] = {}
    for a, b in (("base_mono", "concrete_mono"), ("base_mixed", "concrete_mono"), ("base_mixed", "base_mono")):
        ratios = [x / y for x, y in zip(samples[a], samples[b])]
        info["paired_ratios"][f"{a}_over_{b}"] = {"median": statistics.median(ratios), "min": min(ratios), "max": max(ratios)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    for name, row in info["summary"].items():
        print(f"{name:14s} {row['median']:6.3f} ns/constraint (range {row['min']:.3f}-{row['max']:.3f})")
    for name, row in info["paired_ratios"].items():
        print(f"{name:30s} {row['median']:.3f} (range {row['min']:.3f}-{row['max']:.3f})")
    print(f"generic execute: {info['generic_execute']['tag_compares']} class-tag compares, "
          f"{len(info['generic_execute']['direct_method_calls'])} direct methods, {info['generic_execute']['indirect_calls']} indirect calls")


if __name__ == "__main__":
    main()
