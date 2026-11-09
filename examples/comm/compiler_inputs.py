"""Capture compiler workload imports without executing the workload.

Run in a fresh hosted process for each source: the loader rewrites ASTs and uses
compiler globals, including the driver's special handling of a shadowed ffi.
"""

import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]


def workload_inputs(source, home):
    # The coordinator invokes this helper with -I; select this checkout's loader,
    # independent of PYTHONPATH and modules imported by another workload.
    sys.path.insert(0, str(ROOT))
    from src.pystachy_compiler import diagnostics, program_cache
    from src.pystachy_compiler.loader import Loader
    from src.pystachy_compiler.specs import MODULES

    sys.setrecursionlimit(diagnostics.MAXNEST * 40)
    diagnostics.SRC = source
    # Match driver.main: the source's real directory, ordered PYSTACHY_PATH
    # entries (empty entries ignored), then the selected compiler home's lib/.
    real = os.path.realpath(source)
    dirs = [os.path.dirname(real)]
    dirs.extend(value for value in os.getenv("PYSTACHY_PATH", "").split(":") if value)
    dirs.append(str(Path(home) / "lib"))
    program_cache.start()
    for directory in dirs[:-1]:
        if (program_cache.tracked_exists(directory + "/ffi.py")
                or program_cache.tracked_exists(directory + "/ffi/__init__.py")):
            del MODULES["ffi"]
            break
    with open(source, encoding=diagnostics.RAW) as stream:
        Loader(dirs).program(source, stream.read())

    # These include sources parsed for optional-import lookahead and implicit
    # library helpers, not just modules retained in Loader.mods. Negative probes
    # identify new shadowing files and namespace-to-package changes as inputs.
    files = {}
    for path, snapshot in program_cache.SOURCES.items():
        with open(path, "rb") as stream:
            files[os.path.abspath(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
        if not program_cache._source_matches(path, snapshot):
            raise RuntimeError(f"workload input changed while resolving imports: {path}")
    probes = {}
    for path, snapshot in program_cache.PROBES.items():
        if not program_cache._probe_matches(path, snapshot):
            raise RuntimeError(f"workload import resolution changed while capturing inputs: {path}")
        # The kind is "d" (a directory), "f" (a regular file), "o" (another file) or "0".
        kind, realpath = program_cache._unpack(snapshot)
        probes[os.path.abspath(path)] = {"exists": kind != "0", "kind": kind, "realpath": realpath}
    if not program_cache.VALID[0]:
        raise RuntimeError("workload inputs changed while resolving imports")
    return {"files": files, "probes": probes, "search_path": dirs,
            "source_realpath": real}


if __name__ == "__main__":
    print(json.dumps(workload_inputs(sys.argv[1], sys.argv[2]), sort_keys=True))
