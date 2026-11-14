"""Launch an optional bundled native compiler, otherwise the hosted compiler."""

import os
from pathlib import Path
import subprocess
import sys
import tarfile


def native_compiler(directory: Path) -> Path | None:
    mode = os.environ.get("PYSTACHY_COMPILER", "auto")
    if mode not in ("auto", "hosted", "native"):
        raise SystemExit("pystachy: PYSTACHY_COMPILER must be auto, hosted or native")
    if mode == "hosted":
        return None
    native = directory / "native" / "pystachy"
    if native.is_file() and os.access(native, os.X_OK):
        return native
    if native.exists() or mode == "native":
        raise SystemExit("pystachy: bundled native compiler is missing or not executable; "
                         "set PYSTACHY_COMPILER=hosted to use Python")
    return None


def main() -> None:
    directory = Path(__file__).resolve().parent
    source = directory / "pystachy.py"
    native = native_compiler(directory)
    if not os.environ.get("PYSTACHY_CACHE"):
        cache_home = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
        os.environ["PYSTACHY_CACHE"] = str(Path(cache_home) / "pystachy")
    if (len(sys.argv) >= 3 and sys.argv[1] in ("run", "build", "ext")
        and "PYSTACHY_LLVM" not in os.environ and Path(sys.argv[2]).is_file()):
        from .pystachy_toolchain import ensure_toolchain

        try:
            llvm = ensure_toolchain()
            if llvm is not None and sys.platform == "darwin" and not os.environ.get("SDKROOT"):
                sdk = subprocess.check_output(
                    ["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True, timeout=30,
                )
                os.environ["SDKROOT"] = sdk.strip()
        except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
            raise SystemExit(f"pystachy: cannot provision LLVM: {error}. Set PYSTACHY_LLVM to use host tools.") from None
        if llvm is not None:
            os.environ["PYSTACHY_LLVM"] = str(llvm)
    if native is not None:
        os.environ.setdefault("PYSTACHY_HOME", str(directory))
        os.execv(str(native), [str(native), *sys.argv[1:]])
    # Keep the .py argv[0] used to identify hosted compiler inputs for caching.
    os.execv(sys.executable, [sys.executable, "-E", "-B", str(source), *sys.argv[1:]])
