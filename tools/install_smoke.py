"""Check hosted and installed native JIT/AOT from outside the source checkout.

Run after `make`: python3 tools/install_smoke.py. LLVM must be installed in one
of the supported locations; PYSTACHY_HOME, PYSTACHY_LLVM and PYSTACHY_CACHE are
deliberately removed to exercise discovery and the installed launcher's defaults.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

PROGRAM = '''import fnmatch
from functools import lru_cache
import os
import tempfile


@lru_cache(maxsize=2)
def route(name: str) -> str:
    if fnmatch.fnmatchcase(name, "api.*"):
        return "api"
    if fnmatch.fnmatchcase(name, "worker.[0-9]*"):
        return "worker"
    return "other"


for event in ["api.read", "worker.12", "api.read", "misc", "misc"]:
    print(route(event))
print(route.cache_info())


def inner() -> int:
    try:
        raise ValueError("caught")
    finally:
        print("inner finally")


try:
    inner()
except ValueError as error:
    print(type(error).__name__, str(error))
finally:
    print("outer finally")

directory = tempfile.mkdtemp()
path = os.path.join(directory, "data.txt")
with open(path, "w", encoding="utf-8") as handle:
    handle.write("alpha\\nbeta\\n")
mtime = os.path.getmtime(path)
ctime = os.path.getctime(path)
print("stat", os.path.getsize(path), mtime > 0.0, ctime > 0.0,
      mtime == os.path.getmtime(path), ctime == os.path.getctime(path))
with open(path, "r", encoding="utf-8") as handle:
    print("file", repr(handle.read()))
os.remove(path)
os.rmdir(directory)
print("removed", not os.path.exists(directory))
'''


def execute(command, directory, environment):
    result = subprocess.run(command, cwd=directory, env=environment, capture_output=True,
                            text=True, timeout=180)
    if result.returncode or result.stderr:
        raise RuntimeError(f"{shlex.join(command)}: exit {result.returncode}\n{result.stdout}{result.stderr}")
    return result.stdout


def smoke(compiler):
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        raise RuntimeError(f"native compiler missing: {compiler}; run make first")
    environment = dict(os.environ)
    for name in list(environment):
        if name.startswith("PYSTACHY_"):
            del environment[name]
    with tempfile.TemporaryDirectory(prefix="pystachy-install-smoke-") as temporary:
        directory = Path(temporary)
        work = directory / "outside checkout"
        work.mkdir()
        environment["XDG_CACHE_HOME"] = str(directory / "user cache")
        program = work / "demo.py"
        program.write_text(PROGRAM)
        expected = execute([sys.executable, str(program)], work, environment)
        hosted = [sys.executable, str(ROOT / "pystachy.py")]
        if execute([*hosted, "run", str(program)], work, environment) != expected:
            raise RuntimeError("CPython-hosted JIT output differs from CPython")
        print("hosted JIT: CPython output matches")
        hosted_executable = work / "hosted-demo"
        execute([*hosted, "build", str(program), "-o", str(hosted_executable)], work, environment)
        if execute([str(hosted_executable)], work, environment) != expected:
            raise RuntimeError("CPython-hosted AOT output differs from CPython")
        print("hosted AOT: CPython output matches")
        prefix = directory / "installed prefix"
        # The CLI installs the compiler built by make, rather than a testing stub.
        execute([sys.executable, str(ROOT / "tools/install.py"), "--prefix", str(prefix)],
                work, environment)
        installed = prefix / "bin/pystachy"
        for stress in (False, True):
            current = dict(environment)
            if stress:
                current["PYSTACHY_GC_STRESS"] = "1000"
                current["PYSTACHY_GC_STRESS_PROGRAM"] = "1"
            if execute([str(installed), "run", str(program)], work, current) != expected:
                raise RuntimeError("installed native JIT output differs from CPython")
            executable = work / ("native-demo-stress" if stress else "native-demo")
            execute([str(installed), "build", str(program), "-o", str(executable)], work, current)
            runtime_environment = dict(current, PYSTACHY_GC_STRESS="1") if stress else current
            if execute([str(executable)], work, runtime_environment) != expected:
                raise RuntimeError("installed native AOT output differs from CPython")
            print(f"installed JIT/AOT{' with GC stress' if stress else ''}: CPython output matches")
        cache = Path(environment["XDG_CACHE_HOME"]) / "pystachy"
        if not cache.is_dir() or not list(cache.glob("runtime-*.bc")):
            raise RuntimeError(f"installed compiler did not populate its external cache: {cache}")
        if (prefix / "libexec/pystachy/build").exists():
            raise RuntimeError("installed compiler wrote a cache inside its installation")
        print("installed runtime cache: outside installation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy",
                        help="the compiler already built by make (default: ./pystachy)")
    arguments = parser.parse_args()
    compiler = arguments.compiler.resolve()
    if compiler != ROOT / "pystachy":
        parser.error("installation smoke requires the ./pystachy compiler built by make")
    try:
        smoke(compiler)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"install smoke: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
