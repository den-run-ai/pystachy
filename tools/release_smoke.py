"""Verify a release archive after moving it away from the source checkout.

Usage: python3 tools/release_smoke.py dist/pystachy-VERSION-TARGET.tar.gz
The subprocess PATH contains system utilities and LLVM, with no Python.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

from install_smoke import PROGRAM, execute
from release import binary_target, sha256


def extract(archive, destination):
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        roots = set()
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError(f"unsafe archive path: {member.name}")
            if not (member.isdir() or member.isfile()):
                raise ValueError(f"unsupported archive member: {member.name}")
            roots.add(path.parts[0])
        if len(roots) != 1:
            raise ValueError("release archive must have exactly one root directory")
        # Members have been restricted to ordinary files and directories with
        # relative paths; no symlink, hardlink or device can redirect extraction.
        for member in members:
            output = destination / member.name
            if member.isdir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with handle.extractfile(member) as source, output.open("wb") as target:
                    shutil.copyfileobj(source, target)
            output.chmod(member.mode & 0o777)
    return destination / roots.pop()


def verify_manifest(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    files = {path.relative_to(directory).as_posix(): sha256(path)
             for path in directory.rglob("*") if path.is_file() and path.name != "manifest.json"}
    if manifest.get("schema_version") != 1 or files != manifest.get("files_sha256"):
        raise ValueError("release manifest hashes do not match extracted files")
    if binary_target(directory / "libexec/pystachy/pystachy") != manifest.get("target"):
        raise ValueError("release manifest target does not match the native compiler")
    data = directory / "libexec/pystachy"
    if ((data / "VERSION").read_text(encoding="utf-8").strip() != manifest.get("version")
            or (data / "REVISION").read_text(encoding="utf-8").strip() != manifest.get("commit")):
        raise ValueError("release manifest metadata does not match the native compiler resources")
    return manifest


def llvm_directory(override):
    if override is not None:
        directory = Path(override).resolve()
    else:
        candidates = [Path(path) for path in ("/usr/lib/llvm-18/bin", "/opt/homebrew/opt/llvm@20/bin",
                      "/usr/local/opt/llvm@20/bin", "/home/linuxbrew/.linuxbrew/opt/llvm@18/bin")]
        directory = next((path for path in candidates if all((path / tool).is_file()
                         for tool in ("clang", "opt", "lli", "llvm-link", "llvm-as"))), None)
        if directory is None:
            clang = shutil.which("clang")
            if clang is None:
                raise ValueError("LLVM is missing; install LLVM 18 on Linux or LLVM 20 on macOS")
            directory = Path(clang).parent
    for tool in ("clang", "opt", "lli", "llvm-link", "llvm-as"):
        if not os.access(directory / tool, os.X_OK):
            raise ValueError(f"LLVM tool is missing or not executable: {directory / tool}")
    return directory


def smoke(archive, llvm=None):
    toolchain = llvm_directory(llvm)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    with tempfile.TemporaryDirectory(prefix="pystachy-release-smoke-") as temporary:
        scratch = Path(temporary)
        stage = scratch / "extract"
        stage.mkdir()
        directory = extract(archive, stage)
        manifest = verify_manifest(directory)
        relocated = scratch / "relocated 'release' $literal"
        directory.rename(relocated)
        work = scratch / "outside checkout"
        work.mkdir()
        program = work / "demo.py"
        program.write_text(PROGRAM, encoding="utf-8")
        expected = execute([sys.executable, str(program)], work, environment)
        commands = scratch / "python-free-path"
        commands.mkdir()
        # clang may invoke the system linker/assembler and macOS SDK tools.
        # Add only these commands, not an entire bin directory containing Python.
        for name in ("sh", "dirname", "readlink", "sed", "mkdir", "mv", "rm", "rmdir",
                     "ld", "as", "xcrun", "dsymutil", "uname"):
            command = shutil.which(name)
            if command:
                (commands / name).symlink_to(command)
        environment.update(PATH=str(commands), PYSTACHY_LLVM=str(toolchain),
                           XDG_CACHE_HOME=str(scratch / "user cache"))
        for path in relocated.rglob("*"):
            path.chmod(0o555 if path.is_dir() or os.access(path, os.X_OK) else 0o444)
        relocated.chmod(0o555)
        installed = relocated / "bin/pystachy"
        # Test the common symlink-in-PATH use case after relocation as well.
        (commands / "pystachy").symlink_to(installed)
        version = f"pystachy {manifest['version']} (commit {manifest['commit']})\n"
        # The native executable itself and the symlinked launcher must both report
        # exact release provenance without invoking an external tool or creating a cache.
        native = relocated / "libexec/pystachy/pystachy"
        for executable, path in ((str(native), ""), ("pystachy", str(commands))):
            current = dict(environment, PATH=path, PYSTACHY_LLVM="/unavailable")
            for option in ("--version", "-V"):
                if execute([executable, option], work, current) != version:
                    raise RuntimeError("release compiler version differs from the manifest")
        if (scratch / "user cache").exists():
            raise RuntimeError("--version created a runtime cache")
        print(version.strip() + ": native and installed --version, without LLVM or Python")
        for stress in (False, True):
            current = dict(environment)
            if stress:
                current.update(PYSTACHY_GC_STRESS="1000", PYSTACHY_GC_STRESS_PROGRAM="1")
            if execute(["pystachy", "run", str(program)], work, current) != expected:
                raise RuntimeError("release JIT output differs from CPython")
            executable = work / ("demo-stress" if stress else "demo")
            execute(["pystachy", "build", str(program), "-o", str(executable)], work, current)
            # No compiler or LLVM command is available when the AOT program runs.
            runtime = dict(current, PATH="")
            if stress:
                runtime["PYSTACHY_GC_STRESS"] = "1"
            if execute([str(executable)], work, runtime) != expected:
                raise RuntimeError("release AOT output differs from CPython")
            print(f"relocated release JIT/AOT{' with GC stress' if stress else ''}: CPython output matches")
        cache = Path(environment["XDG_CACHE_HOME"]) / "pystachy"
        if not list(cache.glob("runtime-*.bc")) or (relocated / "libexec/pystachy/build").exists():
            raise RuntimeError("release compiler did not use its external runtime cache")
        print(f"release {manifest['version']} {manifest['target']}: Python-free PATH, read-only resources, external cache")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--llvm", help="LLVM bin directory (default: supported system installation)")
    args = parser.parse_args()
    try:
        smoke(args.archive.resolve(), args.llvm)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, tarfile.TarError) as error:
        parser.exit(1, f"release smoke: {error}\n")


if __name__ == "__main__":
    main()
