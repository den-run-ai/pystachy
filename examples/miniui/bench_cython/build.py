#!/usr/bin/env python3
"""Build explicit miniui comparison variants; do not edit measured Python sources.

Requires Cython 3.1.8, setuptools 80.9.0, CPython headers and a C compiler.
Choose libminiui.so at process launch with LD_LIBRARY_PATH for every variant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
MODES = ("same_source", "cpython_native", "cython_native", "cython_typed")
SENSITIVITY_BASELINES = {
    "same_source_auto": "same_source",
    "cython_native_auto": "cython_native",
    "cython_typed_noexcept": "cython_typed",
}
OPTIONAL_MODES = tuple(SENSITIVITY_BASELINES)
AUTO_MODES = ("same_source_auto", "cython_native_auto")
NATIVE_NAMES = ("_init", "_close", "_open", "_focused", "_mouse_x", "_mouse_y", "_mouse",
                "_keys", "_character", "_dt", "_begin", "_end", "_clip", "_rect", "_text", "_width")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--library-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=(*MODES, *OPTIONAL_MODES, "all"), default="all",
                        help="all builds the original four variants; supplemental modes are opt-in")
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    parser.add_argument("--without-workload", action="store_true")
    args = parser.parse_args()
    from Cython.Build import cythonize
    import Cython
    from setuptools import Distribution, Extension
    if not (args.library_dir / "libminiui.so").is_file():
        parser.error("--library-dir must contain libminiui.so")
    os.environ["CC"] = args.cc
    os.environ["LDSHARED"] = args.cc + " -shared"
    # Avoid inherited profile/coverage/build flags affecting this comparator.
    os.environ.pop("CFLAGS", None)
    os.environ.pop("CPPFLAGS", None)
    os.environ.pop("LDFLAGS", None)
    source_names = ["miniui", "raylib_backend"]
    if not args.without_workload:
        source_names.append("benchmark_workload")
    source_hashes = {name + ".py": hashlib.sha256((SOURCE / (name + ".py")).read_bytes()).hexdigest()
                     for name in source_names}
    backend = (SOURCE / "raylib_backend.py").read_text()
    window = backend[backend.index("class Window:"):]
    bindings = (HERE / "native_bindings.pxi").read_text()
    for mode in MODES if args.mode == "all" else (args.mode,):
        base_mode = SENSITIVITY_BASELINES.get(mode, mode)
        typed = base_mode == "cython_typed"
        infer_types = None if mode in AUTO_MODES else False
        mode_bindings = bindings
        noexcept_helpers = ()
        if mode == "cython_typed_noexcept":
            from typed_codegen import NOEXCEPT_HELPERS, with_scalar_noexcept
            mode_bindings = with_scalar_noexcept(bindings)
            noexcept_helpers = NOEXCEPT_HELPERS
        target = args.output.resolve() / mode
        target.mkdir(parents=True, exist_ok=True)
        for name in source_names:
            shutil.copy2(SOURCE / (name + ".py"), target / (name + ".py"))
        extensions = []
        if base_mode == "cpython_native":
            (target / "miniui_native.pyx").write_text(mode_bindings)
            imports = "from miniui_native import " + ", ".join(NATIVE_NAMES) + "\n"
            (target / "raylib_backend.py").write_text("from miniui import Input, UI\n" + imports + "\n" + window)
            extensions.append(Extension("miniui_native", [str(target / "miniui_native.pyx")],
                include_dirs=[str(HERE)], library_dirs=[str(args.library_dir.resolve())], libraries=["miniui"],
                extra_compile_args=["-O3"], extra_link_args=["-Wl,-z,now"]))
        else:
            if typed:
                from typed_codegen import generate
                generate(target, SOURCE, mode_bindings, not args.without_workload)
            for name in source_names:
                source = target / (name + ".py")
                native = (base_mode == "cython_native" or typed) and name == "raylib_backend"
                if typed:
                    source = target / (name + ".pyx")
                if native and not typed:
                    source = target / "raylib_backend.pyx"
                    source.write_text("from miniui import Input, UI\n" + mode_bindings + "\n" + window)
                extensions.append(Extension(name, [str(source)], include_dirs=[str(HERE)],
                    library_dirs=[str(args.library_dir.resolve())] if native else [],
                    libraries=["miniui"] if native else [], extra_compile_args=["-O3"],
                    extra_link_args=["-Wl,-z,now"] if native else []))
        modules = cythonize(extensions, compiler_directives={
            "language_level": 3, "binding": True, "annotation_typing": True,
            "boundscheck": True, "wraparound": True, "initializedcheck": True,
            "cdivision": False, "infer_types": infer_types,
            "overflowcheck": typed,
        }, build_dir=str(target / "generated"), annotate=False)
        dist = Distribution({"name": "miniui-" + mode, "ext_modules": modules})
        build = dist.get_command_obj("build_ext")
        build.build_lib = str(target)
        build.build_temp = str(target / "temp")
        build.force = True
        dist.run_command("build_ext")
        metadata = {
            "mode": mode, "python": sys.version, "cython": Cython.__version__,
            "compiler": subprocess.run([args.cc, "--version"], check=True, capture_output=True,
                                       text=True).stdout.splitlines()[0],
            "optimization": "-O3; no fast-math; checked integer conversions; GIL held",
            "extension_suffix": sysconfig.get_config_var("EXT_SUFFIX"),
            "source_sha256": source_hashes,
            "generator_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                 for name in ("build.py", "typed_codegen.py", "native_bindings.pxi", "miniui_abi.h")},
            "compiler_so": build.compiler.compiler_so,
            "linker_so": build.compiler.linker_so,
            "overflowcheck": typed,
            "boundscheck": True,
            "wraparound": True,
            "infer_types": infer_types,
            "inference": "Cython default safe inference (infer_types=None)" if infer_types is None else
                "automatic inference disabled (infer_types=False); explicit annotations retained",
            "native_noexcept_helpers": list(noexcept_helpers),
            "native_bindings_sha256": hashlib.sha256(mode_bindings.encode()).hexdigest()
                if base_mode != "same_source" else None,
            "sensitivity_baseline": SENSITIVITY_BASELINES.get(mode),
            "library_dir_for_link": str(args.library_dir.resolve()),
            "runtime_library_selection": "LD_LIBRARY_PATH; no RPATH embedded",
            "python_classes": "extension classes with typed fields and cpdef methods" if typed else "regular classes; not cdef classes",
            "transformations": ("typed fields/hot locals/cpdef methods; cross-module cimport; explicit double unboxing of particle list reads; same Python lists/sets/strings"
                + ("; listed non-raising scalar C helpers declared noexcept" if noexcept_helpers else "")) if typed else "none" if base_mode == "same_source" else
                "replace @ffi.extern declarations with direct typed C calls; preserve Window body",
        }
        (target / "build-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps({"mode": mode, "path": str(target)}), flush=True)


if __name__ == "__main__":
    main()
