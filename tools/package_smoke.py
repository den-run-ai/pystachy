"""Build, resolve and consume the example packages without a package index.

Run after make: python3 tools/package_smoke.py. Requires uv; setuptools is
also needed in the active Python when using --no-build-isolation.
"""

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "Chapter IV\n"


def execute(command, directory, environment, reject=""):
    result = subprocess.run(command, cwd=directory, env=environment, text=True,
                            capture_output=True, timeout=300)
    output = result.stdout + result.stderr
    if reject:
        if result.returncode == 0 or reject.lower() not in output.lower():
            raise RuntimeError(f"expected rejection containing {reject!r}: {shlex.join(command)}\n{output}")
    elif result.returncode:
        raise RuntimeError(f"{shlex.join(command)}: exit {result.returncode}\n{output}")
    return result.stdout


def verify_ports(wheel, expected):
    with zipfile.ZipFile(wheel) as archive:
        missing = expected - set(archive.namelist())
        if missing:
            raise RuntimeError(f"port wheel omitted sources or provenance: {sorted(missing)}")
        for name in expected:
            if archive.read(name) != (ROOT / "ports" / name).read_bytes():
                raise RuntimeError(f"port wheel changed source or provenance: {name}")
        notices = [name for name in archive.namelist() if name.endswith("/THIRD_PARTY_NOTICES")
                   or name == "THIRD_PARTY_NOTICES"]
        original = (ROOT / "THIRD_PARTY_NOTICES").read_bytes()
        if not notices or any(archive.read(name) != original for name in notices):
            raise RuntimeError("port wheel omitted or changed THIRD_PARTY_NOTICES")


def smoke(compiler, no_build_isolation):
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required; install it before running the packaging smoke")
    # Compiler arguments are supplied in the checkout, but every consumer runs
    # elsewhere. Resolve file arguments now, including a hosted compiler script.
    compiler = [str(Path(word).resolve()) if Path(word).is_file() else word
                for word in shlex.split(compiler)]
    if not compiler:
        raise RuntimeError("--compiler must contain a command")
    ports = ROOT / "ports"
    expected = {path.relative_to(ports).as_posix()
                for package in ports.iterdir() if (package / "__init__.py").is_file()
                for path in package.rglob("*") if path.is_file()
                and (path.suffix == ".py" or path.name.startswith("LICENSE")
                     or (path.name.startswith("PORT") and path.suffix == ".md"))}
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYSTACHY_PATH"):
        environment.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="pystachy-package-smoke-") as temporary:
        directory = Path(temporary)
        work = directory / "outside checkout"
        work.mkdir()
        wheelhouse = directory / "wheelhouse"
        wheelhouse.mkdir()
        for source in (ports, ROOT / "examples/package"):
            command = [uv, "build", str(source), "--out-dir", str(wheelhouse),
                       "--python", sys.executable, "--no-python-downloads"]
            if no_build_isolation:
                command.append("--no-build-isolation")
            # uv's default builds an sdist, then builds the wheel from that
            # sdist: both publication formats must contain the actual inputs.
            execute(command, work, environment)
        wheels = sorted(wheelhouse.glob("*.whl"))
        sdists = sorted(wheelhouse.glob("*.tar.gz"))
        if len(wheels) != 2 or len(sdists) != 2:
            raise RuntimeError("expected one source distribution and wheel per package")
        port_wheel = next(path for path in wheels if path.name.startswith("pystachy_ports-"))
        verify_ports(port_wheel, expected)
        print("sdist/wheel: all port sources, licenses and provenance included")

        requirements = work / "requirements.in"
        requirements.write_text("pystachy-demo==0.1.0\n", encoding="utf-8")
        lock = work / "requirements.txt"
        local = ["--no-index", "--find-links", str(wheelhouse), "--only-binary", ":all:"]
        resolve = [uv, "--no-cache", "pip", "compile", str(requirements), *local,
                   "--python", sys.executable, "--no-python-downloads",
                   "--generate-hashes", "--no-header", "--no-annotate", "-o", str(lock)]
        execute(resolve, work, environment)
        locked = lock.read_text(encoding="utf-8")
        if "pystachy-demo==0.1.0" not in locked or "pystachy-ports==0.1.0" not in locked:
            raise RuntimeError("resolver omitted the application or its transitive dependency")
        target = directory / "installed"
        sync = [uv, "--no-cache", "pip", "sync", str(lock), "--require-hashes", *local,
                "--python", sys.executable, "--no-python-downloads", "--target", str(target)]
        execute(sync, work, environment)
        current = dict(environment, PYTHONPATH=str(target), PYSTACHY_PATH=str(target))
        # -S keeps user/system site packages from satisfying an omitted wheel.
        provenance = ("from pathlib import Path; import pystachy_demo, roman; "
                      f"root = Path({str(target)!r}).resolve(); "
                      "assert all(Path(m.__file__).resolve().is_relative_to(root) "
                      "for m in (pystachy_demo, roman))")
        execute([sys.executable, "-S", "-c", provenance], work, current)
        consumer = work / "use.py"
        shutil.copyfile(ROOT / "examples/package/use.py", consumer)
        console = target / "bin/pystachy-demo"
        for command in ([sys.executable, "-S", str(consumer)],
                        [sys.executable, "-S", "-m", "pystachy_demo"],
                        [sys.executable, "-S", str(console)],
                        [*compiler, "run", str(consumer)],
                        [*compiler, "run", str(console)]):
            if execute(command, work, current) != EXPECTED:
                raise RuntimeError(f"installed package output differs: {shlex.join(command)}")
        binaries = [work / "demo", work / "demo-cli"]
        for source, binary in zip((consumer, console), binaries):
            execute([*compiler, "build", str(source), "-o", str(binary)], work, current)
        # Remove every installed source and the entry point. The AOT executable
        # must not need the compiler, LLVM, Python or an import path at runtime.
        shutil.rmtree(target)
        consumer.unlink()
        standalone = dict(environment, PATH="", PYTHONPATH="", PYSTACHY_PATH="")
        for binary in binaries:
            if execute([str(binary)], work, standalone) != EXPECTED:
                raise RuntimeError("standalone AOT output differs from CPython")
        print("offline hashed dependency sync: CPython library/module/CLI, JIT and standalone AOT match")

        requirements.write_text("pystachy-demo==0.1.0\npystachy-ports==999.0\n", encoding="utf-8")
        execute(resolve, work, environment, reject="No solution found")
        # Keep the wheel valid while changing its hash; --no-cache forces uv
        # to inspect the bytes rather than reuse its previous installation.
        with zipfile.ZipFile(port_wheel, "a") as archive:
            archive.writestr("tampered.txt", "changed after locking\n")
        execute(sync, work, environment, reject="hash")
        print("negative checks: incompatible dependency and altered wheel rejected")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="./pystachy", help="compiler command (shell-style arguments)")
    parser.add_argument("--no-build-isolation", action="store_true",
                        help="use setuptools already installed in the active Python")
    arguments = parser.parse_args()
    try:
        smoke(arguments.compiler, arguments.no_build_isolation)
    except (OSError, RuntimeError, StopIteration, subprocess.TimeoutExpired, zipfile.BadZipFile) as error:
        print(f"package smoke: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
