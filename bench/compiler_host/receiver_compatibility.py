"""Rebuild the receiver-typed overlay natively and require compiler/runtime IR witnesses.

The seed, overlay compiler, and optional second native generation all compile
the same unmodified input, the overlay source, and the same runtime source.
Host preparation is separate from the frontend timing harness in run.py.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys

from annotate_receivers import apply
from run import ROOT, atomic_json, bootstrap, measure, sha


def compiler_sources(root):
    paths = [root / "pystachy.py", *(root / "src").rglob("*.py")]
    return {str(path.relative_to(root)): sha(path) for path in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, default=ROOT)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--generations", type=int, choices=(1, 2), default=2)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    work, seed = args.work.resolve(), args.seed.resolve()
    llvm, frozen = args.llvm.resolve(), args.input_root.resolve()
    if not seed.is_file() or not (frozen / "pystachy.py").is_file():
        parser.error("seed and frozen input must exist")
    work.mkdir(parents=True, exist_ok=False)
    overlay = work / "overlay"
    overlay.mkdir()
    shutil.copytree(ROOT / "src", overlay / "src", ignore=shutil.ignore_patterns("__pycache__", "*.so"))
    shutil.copy2(ROOT / "pystachy.py", overlay / "pystachy.py")
    counts = apply(overlay)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update({"PYSTACHY_HOME": str(frozen), "PYSTACHY_PATH": "",
                "PYSTACHY_LLVM": str(llvm), "PYSTACHY_CACHE": str(work / "cache"),
                "PYSTACHY_TIMING": "1", "PYSTACHY_RUNTIME_C_CACHE": "1",
                "PYSTACHY_BUILD_JOBS": "1", "PYTHONHASHSEED": "0"})
    source = bootstrap.source_identity(ROOT)
    input_source = bootstrap.source_identity(frozen)
    overlay_source = compiler_sources(overlay)
    report = {"complete": False, "source": source, "input_source": input_source,
              "overlay_source": overlay_source, "receiver_counts": counts,
              "seed": {"path": str(seed), "sha256": sha(seed)},
              "tools": bootstrap.tool_identity(sys.executable, str(llvm)),
              "host": bootstrap.host_state(), "generations": args.generations,
              "environment": {k: v for k, v in env.items()
                              if k.startswith("PYSTACHY_") or k in ("LD_LIBRARY_PATH", "PYTHONHASHSEED")},
              "builds": [], "witnesses": []}

    def execute(command, environment):
        result = measure.execute(command, environment, args.timeout)
        atomic_json(args.report, report)
        return result

    inputs = (("plain", "ir", frozen / "pystachy.py"),
              ("overlay", "ir", overlay / "pystachy.py"),
              ("runtime", "rt", frozen / "runtime.py"))
    expected = {}

    def witness(compiler, generation):
        for name, mode, path in inputs:
            output = work / f"{generation}-{name}.ll"
            result = execute([str(compiler), mode, str(path), "-o", str(output)], env)
            result.update(generation=generation, input=name,
                          output_sha256=sha(output) if output.is_file() else None)
            report["witnesses"].append(result)
            atomic_json(args.report, report)
            measure.successful(result)
            if result["output_sha256"] is None:
                raise RuntimeError("compiler did not produce IR")
            if generation == "seed":
                expected[name] = result["output_sha256"]
            result["matches_seed"] = result["output_sha256"] == expected[name]
            atomic_json(args.report, report)
            if not result["matches_seed"]:
                raise RuntimeError(f"{generation} {name} IR does not match the seed")
            print(f"{generation} {name}: {result['wall_s']:.3f}s match=True", flush=True)

    try:
        witness(seed, "seed")
        compiler = seed
        for generation in range(1, args.generations + 1):
            built = work / f"native-{generation}"
            retained = work / f"build-{generation}.ll"
            optimize = 0 if generation == 1 else 2
            result = execute([str(compiler), "build", str(overlay / "pystachy.py"),
                              "-o", str(built), "--emit-ir", str(retained)],
                             env | {"PYSTACHY_AOT_OPT": str(optimize)})
            result.update(generation=generation, aot_opt=optimize,
                          executable_sha256=sha(built) if built.is_file() else None,
                          retained_ir_sha256=sha(retained) if retained.is_file() else None)
            report["builds"].append(result)
            atomic_json(args.report, report)
            measure.successful(result)
            result["matches_seed"] = result["retained_ir_sha256"] == expected["overlay"]
            atomic_json(args.report, report)
            if not result["matches_seed"] or result["executable_sha256"] is None:
                raise RuntimeError("native overlay build did not reproduce its seed IR")
            witness(built, f"native-{generation}")
            compiler = built
        report["source_unchanged"] = source == bootstrap.source_identity(ROOT)
        report["input_source_unchanged"] = input_source == bootstrap.source_identity(frozen)
        report["overlay_source_unchanged"] = overlay_source == compiler_sources(overlay)
        report["seed_unchanged"] = report["seed"]["sha256"] == sha(seed)
        report["complete"] = all(report[name] for name in
                                  ("source_unchanged", "input_source_unchanged",
                                   "overlay_source_unchanged", "seed_unchanged"))
        # The plain and overlay inputs differ in annotations, imports, casts and
        # source locations. Their hashes are descriptive, not a required equality.
        report["overlay_vs_plain_ir_equal"] = expected["overlay"] == expected["plain"]
        return 0 if report["complete"] else 1
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        atomic_json(args.report, report)


if __name__ == "__main__":
    sys.exit(main())
