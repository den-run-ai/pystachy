#!/usr/bin/env python3
"""Describe locally built benchmark variants without embedding machine paths."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--llvm", default=os.environ.get("PYSTACHY_LLVM", ""))
    parser.add_argument("--compiler", type=Path, default=root / "pystachy")
    parser.add_argument("--aot", type=Path, default=root / "build/miniui-bench/miniui-aot")
    parser.add_argument("--adapters", type=Path, default=root / "build/miniui-bench/adapters")
    parser.add_argument("--cython", type=Path, default=root / "build/miniui-bench-cython")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--standard-cython", action="store_true",
                        help="use standard safe inference and non-raising typed scalar helpers")
    args = parser.parse_args()
    source = root / "examples/miniui"
    entry = ("import sys; from benchmark_workload import run; "
             "run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), "
             "sys.argv[5] if len(sys.argv)>5 else '')")
    base_path = str(source) + ":" + str(root / "tools/rt_cpython")
    runtimes = [{"name": "cpython_twin", "command": [args.python, "-c", entry],
                 "env": {"PYTHONPATH": base_path}}]
    variants = [("cpython_native", "cpython_native")]
    if args.standard_cython:
        variants.extend([("cython_auto", "same_source_auto"),
                         ("cython_native_auto", "cython_native_auto"),
                         ("cython_typed_noexcept", "cython_typed_noexcept")])
    else:
        variants.extend([("cython_same", "same_source"), ("cython_native", "cython_native"),
                         ("cython_typed", "cython_typed")])
    for name, directory in variants:
        path = args.cython.resolve() / directory
        if not (path / "build-metadata.json").exists():
            parser.error("missing comparison build: " + str(path))
        runtimes.append({"name": name, "command": [args.python, "-c", entry],
                         "env": {"PYTHONPATH": str(path) + ":" + base_path}})
    runtimes.extend([
        {"name": "pystachy_aot", "command": [str(args.aot.resolve())]},
        {"name": "pystachy_jit", "command": [str(args.compiler.resolve()), "run",
                                             str(source / "benchmark_entry.py")]},
    ])
    env = {"PYSTACHY_HOME": str(root)}
    if args.llvm:
        env["PYSTACHY_LLVM"] = args.llvm
    result = {"runtimes": runtimes, "env": env,
              "adapters": {mode: str(args.adapters.resolve() / mode)
                           for mode in ("stub", "verify", "real")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(", ".join(runtime["name"] for runtime in runtimes))


if __name__ == "__main__":
    main()
