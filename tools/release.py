"""Package a bootstrapped native compiler as a relocatable release tarball.

Run `make` first, then `python3 tools/release.py --version v0.1.0`.
LLVM remains an external compilation dependency; Python is only needed to
build this archive, not to use the packaged compiler.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile

from install import DIRS, FILES

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("linux-x86_64", "macos-arm64", "macos-x86_64")
LAUNCHER = '''#!/bin/sh
# Relocatable native Pystachy release; also supports a symlink on PATH.
pystachy_launcher=$0
case "$pystachy_launcher" in
    */*) ;;
    *) pystachy_launcher=$(command -v "$pystachy_launcher") || exit 1 ;;
esac
pystachy_links=0
while [ -L "$pystachy_launcher" ]; do
    pystachy_links=$((pystachy_links + 1))
    if [ "$pystachy_links" -gt 40 ]; then
        echo "pystachy: too many launcher symlinks" >&2
        exit 1
    fi
    pystachy_directory=$(CDPATH= cd -P "$(dirname "$pystachy_launcher")" && pwd) || exit 1
    pystachy_launcher=$(readlink "$pystachy_launcher") || exit 1
    case "$pystachy_launcher" in
        /*) ;;
        *) pystachy_launcher=$pystachy_directory/$pystachy_launcher ;;
    esac
done
pystachy_prefix=$(CDPATH= cd -P "$(dirname "$pystachy_launcher")/.." && pwd) || exit 1
PYSTACHY_HOME=${PYSTACHY_HOME:-"$pystachy_prefix/libexec/pystachy"}
PYSTACHY_CACHE=${PYSTACHY_CACHE:-"${XDG_CACHE_HOME:-$HOME/.cache}/pystachy"}
export PYSTACHY_HOME PYSTACHY_CACHE
exec "$pystachy_prefix/libexec/pystachy/pystachy" "$@"
'''


def host_target():
    system = {"Linux": "linux", "Darwin": "macos"}.get(platform.system())
    machine = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64",
               "aarch64": "arm64"}.get(platform.machine().lower())
    target = f"{system}-{machine}"
    if target not in TARGETS:
        raise ValueError(f"unsupported release host: {platform.system()} {platform.machine()}")
    return target


def binary_target(binary):
    """Read executable headers instead of trusting its name or builder's host."""
    with binary.open("rb") as handle:
        header = handle.read(32)
    if header[:4] == b"\x7fELF" and len(header) >= 20:
        if header[4] == 2 and header[5] in (1, 2):
            endian = "<" if header[5] == 1 else ">"
            kind, machine = struct.unpack(endian + "HH", header[16:20])
            if kind in (2, 3) and machine == 62:
                return "linux-x86_64"
    # Release artifacts are single-architecture executables, rather than fat Mach-O.
    endian = {b"\xcf\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xcf": ">"}.get(header[:4])
    if endian and len(header) >= 16:
        cpu, _, kind = struct.unpack(endian + "III", header[4:16])
        if kind == 2:
            if cpu == 0x01000007:
                return "macos-x86_64"
            if cpu == 0x0100000C:
                return "macos-arm64"
    raise ValueError(f"not a supported native ELF/Mach-O executable: {binary}")


def git_value(source, *arguments):
    return subprocess.check_output(["git", "-C", str(source), *arguments], text=True).strip()


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def copy_resources(source, destination):
    for name in FILES + DIRS:
        path = source / name
        if not path.exists() or path.is_symlink():
            raise ValueError(f"missing or symlinked release input: {path}; run make first")
    if not os.access(source / "pystachy", os.X_OK):
        raise ValueError("the native compiler is not executable; run make first")
    destination.mkdir(parents=True)
    for name in FILES:
        path = source / name
        if not path.is_file():
            raise ValueError(f"release input is not a file: {path}")
        shutil.copyfile(path, destination / name)
    for name in DIRS:
        path = source / name
        if not path.is_dir():
            raise ValueError(f"release input is not a directory: {path}")
        # Keep only runtime sources and their provenance. Never package caches,
        # local build products, or unexpected files from a working checkout.
        for entry in sorted(path.rglob("*")):
            relative = entry.relative_to(path)
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if entry.is_symlink():
                raise ValueError(f"symlink in release resources: {entry}")
            if entry.is_dir():
                continue
            allowed = entry.suffix == ".py" if name == "lib" else entry.suffix in (".c", ".h")
            allowed = allowed or entry.suffix == ".md" or entry.name.startswith("LICENSE")
            if not allowed:
                continue
            if not entry.is_file():
                raise ValueError(f"release resource is not a file: {entry}")
            output = destination / name / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, output)
    (destination / "pystachy").chmod(0o755)


def archive_tree(directory, output, epoch):
    """Canonical order, permissions, owners and timestamps; deterministic gzip."""
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in [directory, *sorted(directory.rglob("*"))]:
                    relative = path.relative_to(directory.parent).as_posix()
                    info = archive.gettarinfo(str(path), arcname=relative)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = epoch
                    info.pax_headers = {}
                    info.mode = 0o755 if path.is_dir() or relative.endswith("/bin/pystachy") or relative.endswith("/libexec/pystachy/pystachy") else 0o644
                    if path.is_file():
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
                    else:
                        archive.addfile(info)


def package(source, output_dir, version, target, commit, epoch):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version):
        raise ValueError("version must be a single safe filename component")
    if target not in TARGETS:
        raise ValueError(f"unsupported target: {target}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("commit must be a full 40-character Git commit SHA")
    if not 0 <= epoch <= 0xFFFFFFFF:
        raise ValueError("SOURCE_DATE_EPOCH must fit gzip's unsigned 32-bit timestamp")
    if binary_target(source / "pystachy") != target:
        raise ValueError(f"native compiler architecture does not match target {target}")
    basename = f"pystachy-{version}-{target}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (basename + ".tar.gz")
    checksum = output_dir / (output.name + ".sha256")
    with tempfile.TemporaryDirectory(prefix="pystachy-release-") as temporary:
        directory = Path(temporary) / basename
        data = directory / "libexec/pystachy"
        copy_resources(source, data)
        (data / "VERSION").write_text(version + "\n", encoding="utf-8")
        (data / "REVISION").write_text(commit + "\n", encoding="utf-8")
        (directory / "bin").mkdir()
        (directory / "bin/pystachy").write_text(LAUNCHER, encoding="utf-8")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES"):
            shutil.copyfile(source / name, directory / name)
        llvm = 18 if target.startswith("linux-") else 20
        requirements = "Ubuntu 24.04 or newer (glibc 2.39+)" if target.startswith("linux-") else "macOS 15 or newer; Xcode Command Line Tools"
        readme = (
            f"Pystachy {version} ({target})\nCommit: {commit}\n\n"
            "Extract this directory anywhere and add its bin/ directory to PATH.\n"
            "The directory can be moved; bin/pystachy can also be symlinked into PATH.\n"
            "Python is not required to use this native compiler.\n"
            f"System requirements: {requirements}.\n"
            f"Compilation requires external LLVM {llvm}: clang, opt, lli, llvm-link, llvm-as.\n"
            f"Install {'clang-18 llvm-18 llvm-18-runtime with apt' if llvm == 18 else 'llvm@20 with Homebrew'}.\n"
            "Use PYSTACHY_LLVM=/path/to/llvm/bin for a nonstandard installation.\n"
            "Run: bin/pystachy run demo.py\n"
            "Build: bin/pystachy build demo.py -o demo\n"
            "Ordinary AOT executables require neither Python nor LLVM to run.\n"
            "Runtime caches use ${XDG_CACHE_HOME:-$HOME/.cache}/pystachy; override with PYSTACHY_CACHE.\n"
            "See https://github.com/den-run-ai/pystachy/blob/main/docs/install.md\n"
        )
        (directory / "README.txt").write_text(readme, encoding="utf-8")
        files = {path.relative_to(directory).as_posix(): sha256(path)
                 for path in sorted(directory.rglob("*")) if path.is_file()}
        manifest = {"schema_version": 1, "name": "pystachy", "version": version,
                    "commit": commit, "target": target, "source_date_epoch": epoch,
                    "llvm_major": llvm, "requirements": requirements, "files_sha256": files}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # Finish the complete archive before replacing a prior output.
        with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as handle:
            staged = Path(handle.name)
        try:
            archive_tree(directory, staged, epoch)
            staged.replace(output)
        finally:
            staged.unlink(missing_ok=True)
    checksum.write_text(f"{sha256(output)}  {output.name}\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT, help="checkout containing the bootstrapped ./pystachy")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", required=True, help="release tag, for example v0.1.0")
    parser.add_argument("--target", choices=TARGETS, help="defaults to the native build host")
    parser.add_argument("--commit", help="defaults to source checkout HEAD")
    parser.add_argument("--epoch", type=int, help="defaults to SOURCE_DATE_EPOCH or commit timestamp")
    args = parser.parse_args()
    try:
        source = args.source.resolve()
        commit = args.commit or git_value(source, "rev-parse", "HEAD")
        epoch = args.epoch
        if epoch is None:
            epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or git_value(source, "show", "-s", "--format=%ct", commit))
        result = package(source, args.output_dir.resolve(), args.version,
                         args.target or host_target(), commit, epoch)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"release: {error}\n")
    print(result)
    print(str(result) + ".sha256")


if __name__ == "__main__":
    main()
