"""Launch the hosted compiler installed by pip or uv."""

import os
from pathlib import Path
import subprocess
import sys
import tarfile


def main() -> None:
    source = Path(__file__).resolve().parent / "pystachy.py"
    if not os.environ.get("PYSTACHY_CACHE"):
        cache_home = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
        os.environ["PYSTACHY_CACHE"] = str(Path(cache_home) / "pystachy")
    # Keep the .py argv[0] used to identify hosted compiler inputs for caching.
    command = [sys.executable, "-E", "-B", str(source), *sys.argv[1:]]
    if sys.argv[1:] == ["doctor"] and "PYSTACHY_LLVM" not in os.environ:
        from .pystachy_toolchain import available, managed_toolchain

        installation = managed_toolchain()
        if installation is not None:
            destination, version, _ = installation
            llvm_bin = destination / "bin"
            ready = available(llvm_bin, version)
            status = "cached" if ready else "pending download on first compile"
            print(f"Managed LLVM {version}: {status}", flush=True)
            os.environ["PYSTACHY_LLVM"] = str(llvm_bin)
            if not ready:
                # Even if every binary answers --version, missing headers require a download.
                raise SystemExit(subprocess.run(command).returncode or 1)
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
    os.execv(sys.executable, command)
