"""Install the native compiler with its runtime, libraries and licenses."""

import argparse
import os
from pathlib import Path
import shlex
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ("pystachy", "runtime.c", "runtime.py", "pyext.c", "pyembed.c", "LICENSE", "THIRD_PARTY_NOTICES")
DIRS = ("lib", "ryu")
MARKER = "# Installed by Pystachy tools/install.py"


def paths(prefix: Path, destdir: Path | None) -> tuple[Path, Path, Path]:
    prefix = Path(os.path.normpath(prefix.expanduser()))
    if not prefix.is_absolute():
        raise ValueError("prefix must be an absolute path")
    # DESTDIR stages files without changing the paths embedded in the launcher.
    root = destdir / prefix.relative_to(prefix.anchor) if destdir else prefix
    return root / "bin/pystachy", root / "libexec/pystachy", prefix / "libexec/pystachy"


def install(prefix: Path, destdir: Path | None = None, source: Path = ROOT) -> None:
    launcher, data, final = paths(prefix, destdir)
    for name in FILES + DIRS:
        if not (source / name).exists():
            raise ValueError(f"missing {source / name}; run make first")
    if not os.access(source / "pystachy", os.X_OK):
        raise ValueError("the native compiler is not executable; run make first")
    if launcher.is_symlink() or (launcher.exists() and MARKER not in launcher.read_text()):
        raise ValueError(f"refusing to replace an unmanaged launcher: {launcher}")
    receipt = data / ".pystachy-install"
    if data.is_symlink() or (data.exists() and (not receipt.is_file() or receipt.read_text() != MARKER)):
        raise ValueError(f"refusing to replace an unmanaged directory: {data}")
    launcher.parent.mkdir(parents=True, exist_ok=True)
    data.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pystachy-", dir=data.parent) as temp:
        staged = Path(temp) / "data"
        staged.mkdir()
        for name in FILES:
            shutil.copyfile(source / name, staged / name)
            (staged / name).chmod(0o755 if name == "pystachy" else 0o644)
        for name in DIRS:
            shutil.copytree(source / name, staged / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (staged / ".pystachy-install").write_text(MARKER)
        if data.exists():
            shutil.rmtree(data)
        staged.rename(data)
    text = (
        "#!/bin/sh\n" + MARKER + "\n"
        f"PYSTACHY_HOME=${{PYSTACHY_HOME:-{shlex.quote(str(final))}}}\n"
        'PYSTACHY_CACHE=${PYSTACHY_CACHE:-"${XDG_CACHE_HOME:-$HOME/.cache}/pystachy"}\n'
        "export PYSTACHY_HOME PYSTACHY_CACHE\n"
        f"exec {shlex.quote(str(final / 'pystachy'))} \"$@\"\n"
    )
    # Publish the complete launcher rather than expose a partially written script.
    with tempfile.NamedTemporaryFile(mode="w", dir=launcher.parent, delete=False) as file:
        temp_launcher = Path(file.name)
        file.write(text)
    temp_launcher.chmod(0o755)
    temp_launcher.replace(launcher)
    print(f"installed {launcher}")


def uninstall(prefix: Path, destdir: Path | None = None) -> None:
    launcher, data, _ = paths(prefix, destdir)
    receipt = data / ".pystachy-install"
    if launcher.is_symlink() or (launcher.exists() and MARKER not in launcher.read_text()):
        raise ValueError(f"refusing to remove an unmanaged launcher: {launcher}")
    if data.is_symlink() or (data.exists() and (not receipt.is_file() or receipt.read_text() != MARKER)):
        raise ValueError(f"refusing to remove an unmanaged directory: {data}")
    launcher.unlink(missing_ok=True)
    if data.exists():
        shutil.rmtree(data)
    print(f"removed {launcher} and {data}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local")
    parser.add_argument("--destdir", type=Path)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    try:
        if args.uninstall:
            uninstall(args.prefix, args.destdir)
        else:
            install(args.prefix, args.destdir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"install: {error}\n")


if __name__ == "__main__":
    main()
