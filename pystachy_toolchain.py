"""Provision the pinned LLVM used by GitHub source installations."""

import hashlib
import http.client
import os
from pathlib import Path
import platform
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


TOOLS = ("clang", "lli", "llvm-as", "llvm-link", "opt")
UBUNTU_SNAPSHOT = "https://snapshot.ubuntu.com/ubuntu/20260828T000000Z"
UBUNTU_REVISION = "18.1.3-1ubuntu1"
# Package hashes come from the Ubuntu archive's signed noble-updates indexes.
UBUNTU_PACKAGES = (
    ("main", "libclang-cpp18",
     "e91eda104813ee0468d145d010a4a4e142401f3f17f9a65596c66d416298d018",
     "f04cf0e22e25fb4706b2175a7c262c20caae8259b442816207fc68a142e63627"),
    ("main", "libllvm18",
     "af6197096ce3b89aab86de59f01c1b5feb008b2ae1514a03906c0664edb8b0b1",
     "9fdecc60d0528466bfbbc141aefd2788ab3bc5459a9ff9c9261fe067a3af3b5c"),
    ("universe", "clang-18",
     "628b16701014ef7ad648380b20ea74b90dd543857f933b3e34d2fc042783de25",
     "e3a70e054d3c0d0841cd7d1555deeab82d75609d34438b1cfc1b187b0add7d77"),
    ("universe", "libclang-common-18-dev",
     "d41631bb752815a8196261d1030c096591c59678c8adfbf2e6a740a691b49e80",
     "b9475c49e5613ce2f98630a269864fb34651e3de275d40dffb2dbdc9863f7fb9"),
    ("universe", "libclang-rt-18-dev",
     "82d5d27d12c0abdf4cefbafa6044e7544a4cbbbec9c04784f5ce326979842b2b",
     "beeaeb2d07108677b2c1b6c4dd18501538e103d585f461cd736cd5f4fc6b98a8"),
    ("universe", "llvm-18",
     "139cb82e16e75fcdd4a56562804ff9bfb482b65d0929580d621d28088075a27e",
     "1d9c87ff9fe17d0ee00703ec0f339ab687e2807b3508b51cf517e05281de104d"),
    ("universe", "llvm-18-runtime",
     "1ad04ff658929491f8bf30fcf6454e07b1815a2b04164f1894156e92c91ef895",
     "b2c829cec030a9bab4fd27b92303eb8491140ad91edf62d55d5b1f8f3d6ef100"),
)
MACOS_VERSION = "20.1.8"
MACOS_RELEASE = (
    f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{MACOS_VERSION}"
    f"/LLVM-{MACOS_VERSION}-macOS-ARM64.tar.xz"
)
MACOS_SHA256 = "a9a22f450d35f1f73cd61ab6a17c6f27d8f6051d56197395c1eb397f0c9bbec4"


# The connection to an endpoint failed or ended early: refused, reset, closed, cut short or
# dropped inside TLS. Like a timeout, each says that endpoint is unavailable now, so it is
# retried and falls back to the mirror. Certificate errors, proxy rejections and anything
# unrecognized stay terminal.
CONNECTION_FAILURES = (ConnectionError, http.client.HTTPException, ssl.SSLEOFError, ssl.SSLZeroReturnError)
NETWORK_FAILURES = (URLError, TimeoutError, *CONNECTION_FAILURES)


def download(url: str, sha256: str, destination: Path, *, fallback_url: str | None = None) -> None:
    # Share the retry budget across endpoints: snapshot, mirror, snapshot. The
    # mirror may prune old packages, so its 404 can use the final snapshot attempt.
    urls = (url, fallback_url or url, url)
    failures = []
    for attempt in range(3):
        active_url = urls[attempt]
        digest = hashlib.sha256()
        error = None
        # Catch network operations separately so local file errors are not retried.
        try:
            response = urlopen(active_url, timeout=60)
        except NETWORK_FAILURES as failure:
            error = failure
        else:
            with response, destination.open("wb") as archive:
                while True:
                    try:
                        chunk = response.read(1024 * 1024)
                    except NETWORK_FAILURES as failure:
                        error = failure
                        break
                    if not chunk:
                        break
                    digest.update(chunk)
                    archive.write(chunk)
        if error is None:
            if digest.hexdigest() != sha256:
                raise ValueError(f"LLVM download checksum mismatch: {active_url}")
            return
        failures.append(f"attempt {attempt + 1} {active_url}: {error}")
        if isinstance(error, HTTPError):
            retryable = error.code in (408, 429, 500, 502, 503, 504)
            retryable = retryable or (attempt == 1 and fallback_url is not None and error.code == 404)
        else:
            reason = error.reason if isinstance(error, URLError) else error
            retryable = (isinstance(reason, (TimeoutError, *CONNECTION_FAILURES))
                         or isinstance(reason, socket.gaierror) and reason.errno == socket.EAI_AGAIN)
        if isinstance(error, HTTPError):
            error.close()
        if not retryable or attempt == 2:
            raise URLError("; ".join(failures)) from error
        time.sleep(attempt + 1)


def unpack_ubuntu(staging: Path, payload: Path, arch: str) -> Path:
    archive = staging / "package.deb"
    for component, package, amd64_hash, arm64_hash in UBUNTU_PACKAGES:
        filename = f"{package}_{UBUNTU_REVISION}_{arch}.deb"
        path = f"pool/{component}/l/llvm-toolchain-18/{filename}"
        mirror = ("https://archive.ubuntu.com/ubuntu" if arch == "amd64"
                  else "https://ports.ubuntu.com/ubuntu-ports")
        download(f"{UBUNTU_SNAPSHOT}/{path}", amd64_hash if arch == "amd64" else arm64_hash,
                 archive, fallback_url=f"{mirror}/{path}")
        subprocess.run(["dpkg-deb", "--extract", str(archive), str(payload)], check=True)
    return payload / "usr/lib/llvm-18/bin"


def unpack_macos(staging: Path, payload: Path) -> Path:
    archive = staging / "llvm.tar.xz"
    download(MACOS_RELEASE, MACOS_SHA256, archive)
    # These upstream binaries link only system libraries. Keep their aliases,
    # Clang's headers and runtimes, and any bundled notices.
    root = f"LLVM-{MACOS_VERSION}-macOS-ARM64"
    tools = (*TOOLS, "clang-20", "dsymutil", "ld64.lld", "lld", "llvm-symbolizer")
    extract_options = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
    with tarfile.open(archive, "r|xz") as source:
        for member in source:
            parts = Path(member.name).parts
            if parts[:1] != (root,):
                continue
            subpath = parts[1:]
            if ((len(subpath) == 2 and subpath[0] == "bin" and subpath[1] in tools)
                or subpath[:2] == ("lib", "clang")
                or (len(subpath) == 1 and parts[-1].startswith(("LICENSE", "NOTICE")))):
                source.extract(member, payload, **extract_options)
    tool_dir = payload / root / "bin"
    if not tool_dir.is_dir():
        raise ValueError("the LLVM archive has an unexpected directory layout")
    return tool_dir


def available(bin_dir: Path, version: str) -> bool:
    major = version.split(".")[0]
    header = bin_dir.resolve().parent / f"lib/clang/{major}/include/stddef.h"
    return header.is_file() and all(
        (bin_dir / name).is_file() and os.access(bin_dir / name, os.X_OK) for name in TOOLS
    )


def ensure_toolchain() -> Path | None:
    machine = platform.machine()
    if sys.platform == "linux" and machine in ("x86_64", "aarch64"):
        try:
            distro = platform.freedesktop_os_release()
        except OSError:
            return None
        if (distro.get("ID"), distro.get("VERSION_ID")) != ("ubuntu", "24.04"):
            return None
        arch = "amd64" if machine == "x86_64" else "arm64"
        key = f"ubuntu-{UBUNTU_REVISION}-{arch}"
        version = "18.1.3"
    elif sys.platform == "darwin" and machine == "arm64":
        key = f"macos-{MACOS_VERSION}-arm64"
        version = MACOS_VERSION
    else:
        return None

    import fcntl

    cache_home = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    cache = Path(os.environ.get("PYSTACHY_LLVM_CACHE") or cache_home / "pystachy/toolchains")
    cache = cache.expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / key
    with (cache / f"{key}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if available(destination / "bin", version):
            return destination / "bin"
        if sys.stderr.isatty():
            print(f"Downloading LLVM {version} to {destination} on first use.", file=sys.stderr, flush=True)
        with tempfile.TemporaryDirectory(prefix=f".{key}-", dir=cache) as temporary:
            staging = Path(temporary)
            payload = staging / "payload"
            if sys.platform == "linux":
                tool_dir = unpack_ubuntu(staging, payload, arch)
            else:
                tool_dir = unpack_macos(staging, payload)
            if not available(tool_dir, version):
                raise ValueError("the LLVM archive is missing required tools or Clang headers")
            for tool in TOOLS:
                result = subprocess.check_output(
                    [str(tool_dir / tool), "--version"], text=True, timeout=30,
                )
                if f"version {version}" not in result:
                    raise ValueError(f"expected LLVM {version} from {tool}, got {result.strip()}")
            (payload / "bin").symlink_to(tool_dir.relative_to(payload), target_is_directory=True)
            if destination.exists():
                shutil.rmtree(destination)
            payload.rename(destination)
    return destination / "bin"
