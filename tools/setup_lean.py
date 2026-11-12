#!/usr/bin/env python3
"""Restore the pinned Lean archive, verify its bytes and extract a fresh toolchain."""

import argparse
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile


VERSION = "4.35.0"
SHA256 = "7289597a44543246c9227b8cae501767e095ce17f6d448b95fc4a8dc97268f6d"
URL = f"https://github.com/leanprover/lean4/releases/download/v{VERSION}/lean-{VERSION}-linux.tar.zst"


def valid_archive(path):
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == SHA256


def install(cache, output):
    """Cache only verified release bytes; never reuse an extracted binary or a proof result."""
    if (platform.system(), platform.machine()) != ("Linux", "x86_64"):
        raise ValueError("the pinned Lean archive requires Linux x86_64")
    output = output.absolute()
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Lean extraction directory must be empty and not a symlink")
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f"{SHA256}.tar.zst"
    if not valid_archive(archive):
        # A corrupt cache must never reach tar. Download and verify a separate file before
        # atomically replacing it, so an interrupted fetch cannot leave a partial cache hit.
        with tempfile.NamedTemporaryFile(dir=cache, suffix=".download", delete=False) as download:
            pending = Path(download.name)
        try:
            subprocess.run([
                "curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
                "--retry-max-time", "240", "--connect-timeout", "20", "--max-time", "120",
                URL, "--output", str(pending),
            ], check=True, timeout=300, stdout=sys.stderr)
            if not valid_archive(pending):
                raise ValueError("downloaded Lean archive SHA256 does not match the pinned release")
            os.replace(pending, archive)
        finally:
            pending.unlink(missing_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(["tar", "--no-same-owner", "--zstd", "-xf", str(archive), "-C", str(output)],
                   check=True, timeout=120, stdout=sys.stderr)
    binary = output / f"lean-{VERSION}-linux/bin"
    if not all((binary / tool).is_file() and os.access(binary / tool, os.X_OK) for tool in ("lean", "lake")):
        raise ValueError("the verified Lean archive did not provide lean and lake executables")
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache/pystachy/lean")
    parser.add_argument("--output", type=Path, required=True, help="fresh extraction directory, removed by caller")
    args = parser.parse_args()
    try:
        print(install(args.cache, args.output))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Lean setup: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
