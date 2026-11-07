"""Run the optional DLPack bridge through real twin/JIT/AOT/extension consumers."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy")
    args = parser.parse_args()
    compiler = str(args.compiler.resolve())
    libname = sysconfig.get_config_var("INSTSONAME") or ""
    candidates = [Path(sys.base_prefix) / "lib" / libname,
                  Path(sysconfig.get_config_var("LIBDIR") or "") / libname]
    libpython = next((p for p in candidates if ".so" in libname and p.is_file()), None)
    if libpython is None or sys.version_info < (3, 12):
        parser.error("the native smoke requires Linux CPython >= 3.12 with shared libpython")

    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") or key == "PYSTACHY_LLVM"}
    paths = [str(ROOT / "tools"), str(EXAMPLE), sysconfig.get_path("purelib"),
             sysconfig.get_path("platlib")]
    env.update(PYTHONPATH=os.pathsep.join(dict.fromkeys(paths)),
               PYSTACHY_HOME=str(ROOT), PYSTACHY_LIBPYTHON=str(libpython),
               PYSTACHY_IRCHECK="1", PYSTACHY_JOBS="2",
               PYSTACHY_GC_STRESS="0", PYSTACHY_GC_STRESS_PROGRAM="0")
    env.pop("PYTHONHOME", None)

    def run(label, command, settings=None):
        print(label, flush=True)
        subprocess.run(command, cwd=ROOT, env=env | (settings or {}),
                       check=True, timeout=180)

    print(f"CPython {sys.version.split()[0]}, NumPy {np.__version__}", flush=True)
    with tempfile.TemporaryDirectory(prefix="pystachy-dlpack-") as temporary:
        tmp = Path(temporary)
        env["PYSTACHY_CACHE"] = str(tmp / "cache")
        source = str(EXAMPLE / "dlpack_score.py")
        run("CPython twin", [sys.executable, source],
            {"PYTHONPATH": str(ROOT / "tools" / "rt_cpython") + os.pathsep + env["PYTHONPATH"]})
        env["PYTHONHOME"] = sys.base_prefix
        for stress in ("0", "1"):
            run(f"native JIT, GC={stress}", [compiler, "run", source],
                {"PYSTACHY_GC_STRESS_PROGRAM": stress})
        program = str(tmp / "score")
        run("build AOT", [compiler, "build", source, "-o", program])
        for stress in ("0", "1"):
            run(f"native AOT, GC={stress}", [program], {"PYSTACHY_GC_STRESS": stress})
        extension = str(tmp / "dlpack_score.abi3.so")
        run("build abi3 extension", [compiler, "ext", source, "--abi", "abi3", "-o", extension])
        for stress in ("0", "1"):
            run(f"native extension, GC={stress}",
                [sys.executable, "-c", 'import dlpack_score; '
                 'assert dlpack_score.__file__.endswith(".so"); dlpack_score.smoke()'],
                {"PYTHONPATH": str(tmp) + os.pathsep + env["PYTHONPATH"],
                 "PYSTACHY_GC_STRESS": stress})
    print("PASS 7 executions: twin and native JIT/AOT/extension with GC 0/1", flush=True)


if __name__ == "__main__":
    main()
