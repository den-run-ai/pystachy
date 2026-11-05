"""Prepare an unchanged compiler copy with mypyc or Cython, outside the checkout.

The Cython control disables annotation typing to preserve Python semantics.
Each phase is separately repeatable; --jobs bounds C compilations within a shared
extension as well as between extensions. No runtime monkeypatch is installed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import sys
import time

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext


ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("name", "sources", "include_dirs", "define_macros", "undef_macros",
          "library_dirs", "libraries", "runtime_library_dirs", "extra_objects",
          "extra_compile_args", "extra_link_args", "depends", "language")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("mypyc", "cython"), required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "generate", "compile"), default="all")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--opt", choices=("0", "1", "2", "3"), default="2")
    parser.add_argument("--receivers", action="store_true", help="explicit mypyc receiver-annotation overlay")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("jobs must be 1..8")
    work = args.work.resolve()
    started = time.monotonic()
    if args.phase != "compile":
        work.mkdir(parents=True, exist_ok=False)
        shutil.copytree(ROOT / "src", work / "src", ignore=shutil.ignore_patterns("__pycache__", "*.so"))
        for name in ("pystachy.py", "mypy.ini"):
            shutil.copy2(ROOT / name, work / name)
    os.chdir(work)
    sys.path.insert(0, str(work))
    phases = {"kind": args.kind, "jobs": args.jobs, "opt": args.opt, "phase": args.phase}
    if args.receivers and args.phase != "compile":
        if args.kind != "mypyc":
            parser.error("receiver overlay is a separate mypyc experiment")
        from annotate_receivers import apply
        phases["receiver_annotations"] = apply(work)
    if args.phase != "compile":
        paths = sorted(str(p) for p in Path("src").rglob("*.py"))
        begin = time.monotonic()
        if args.kind == "mypyc":
            from mypyc.build import mypycify
            extensions = mypycify(paths, opt_level=args.opt, debug_level="0", multi_file=True)
        else:
            from Cython.Build import cythonize
            extensions = cythonize(paths, compiler_directives={"language_level": 3,
                                    "annotation_typing": False, "infer_types": False},
                                    nthreads=args.jobs, quiet=True)
            for ext in extensions:
                ext.extra_compile_args = ["-O" + args.opt, "-g0"]
        phases["generate_s"] = time.monotonic() - begin
        Path("extensions.json").write_text(json.dumps([{k: getattr(ext, k) for k in FIELDS}
                                                      for ext in extensions], indent=2) + "\n")
        Path("generation.json").write_text(json.dumps(phases, indent=2) + "\n")
    else:
        generated = json.loads(Path("generation.json").read_text())
        if generated["kind"] != args.kind or generated["opt"] != args.opt:
            parser.error("compile options must match the recorded generation options")
        extensions = [Extension(**spec) for spec in json.loads(Path("extensions.json").read_text())]
    if args.phase != "generate":
        class BoundedBuild(build_ext):
            def build_extensions(self):
                if args.kind == "cython":
                    # Cython has one C source per extension; setuptools can
                    # schedule those extensions directly within the same budget.
                    self.parallel = args.jobs
                    super().build_extensions()
                    return
                # build_ext -j schedules extensions, leaving one large mypyc group
                # sequential. Queue its individual C units, then join before link.
                self.parallel = None
                original_compile = self.compiler._compile
                original_batch = self.compiler.compile
                with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                    pending = []

                    def compile_one(*positional, **keywords):
                        pending.append(pool.submit(original_compile, *positional, **keywords))

                    def compile_batch(*positional, **keywords):
                        try:
                            objects = original_batch(*positional, **keywords)
                            for future in pending:
                                future.result()
                            return objects
                        finally:
                            for future in pending:
                                future.cancel()
                            pending.clear()

                    self.compiler._compile = compile_one
                    self.compiler.compile = compile_batch
                    try:
                        super().build_extensions()
                    finally:
                        self.compiler._compile = original_compile
                        self.compiler.compile = original_batch

        begin = time.monotonic()
        setup(name="pystachy-compiler-host-probe", ext_modules=extensions,
              cmdclass={"build_ext": BoundedBuild},
              script_args=["build_ext", "--inplace", "--force"])
        phases["compile_link_s"] = time.monotonic() - begin
    phases["total_s"] = time.monotonic() - started
    Path(f"preparation-{args.phase}-{args.jobs}.json").write_text(json.dumps(phases, indent=2) + "\n")
    print(json.dumps(phases), flush=True)


if __name__ == "__main__":
    main()
