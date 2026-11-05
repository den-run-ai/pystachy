"""Record current first blockers for whole mypy/mypyc entry points.

An import rejection is not an exhaustive compatibility audit. The supplied source
root is inventoried, including installed-wheel .py sources when used as input.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import os
from pathlib import Path
import sys

from run import ROOT, atomic_json, measure, sha


PROBES = {
    "mypy_api": "from mypy.api import run\nprint(run(['--version']))\n",
    "mypy_main": "from mypy.main import main\n",
    "mypy_fastparse": "from mypy.fastparse import parse\n",
    "mypy_mro": "from mypy.mro import linearize_hierarchy\n",
    "mypyc_build": "from mypyc.build import mypycify\n",
    "dict_subclass": "class SymbolTable(dict[str, int]):\n    pass\nprint(SymbolTable())\n",
    "module_globals": "print(len(globals()))\n",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    sources = {str(p.relative_to(args.source)): sha(p) for name in ("mypy", "mypyc", "librt")
               for p in (args.source / name).rglob("*.py")}
    if not sources:
        parser.error("no package Python sources found")
    report = {"source_files": sources, "compiler_sha256": sha(args.compiler),
              "installed_mypy_version": importlib.metadata.version("mypy"), "results": {}}
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update({"PYSTACHY_HOME": str(ROOT), "PYSTACHY_PATH": str(args.source.resolve())})
    for name, source in PROBES.items():
        path = work / f"{name}.py"
        path.write_text(source)
        result = measure.execute([str(args.compiler.resolve()), "ir", str(path), "-o", str(work / f"{name}.ll")], env, 60)
        report["results"][name] = result
        print(name, result["exit_code"], result["stderr"].strip(), flush=True)
        atomic_json(args.report, report)


if __name__ == "__main__":
    sys.exit(main())
