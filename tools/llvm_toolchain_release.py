"""Publish a built LLVM toolchain archive as the asset of its own GitHub release.

The release is llvm-toolchain-<LLVM release>-<revision>: it is not a Pystachy version, and it must
never be the repository's latest release, which names the newest stable Pystachy. The release is a
draft until its archive has been read back. A published one is not changed: the same archive
passes, and another needs the next revision. Authenticate gh first (GH_TOKEN).
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pystachy_toolchain

ARCHIVE = re.compile(r"pystachy-llvm-([0-9]+\.[0-9]+\.[0-9]+)-linux-(?:x86_64|aarch64)\.tar\.xz")
NOTES = """\
The minimal LLVM {release} toolchain for Pystachy on Linux: `clang`, `opt`, `lli`, `llc`, `llvm-link` \
and `llvm-as` over one single-target `libLLVM`. This is not a Pystachy release.

`{name}` has SHA-256 `{digest}`. It was built at {repository}@{commit} by `tools/llvm_toolchain.sh`: \
[contents, build and check](https://github.com/{repository}/blob/{commit}/docs/llvm-toolchain.md). \
LLVM's license is in the archive's `share/licenses`.
"""


def gh(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *arguments], capture_output=True, text=True, timeout=600)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def publish(repository: str, commit: str, revision: str, archive: Path, run=gh, pinned=None) -> str:
    """Publish the archive and return what was done; run stands in for gh in tests.

    pinned is the (archive name, revision, SHA-256) that pystachy_toolchain.py downloads: that
    revision may hold no other bytes, or every download of it would fail its check.
    """
    named = ARCHIVE.fullmatch(archive.name)
    if not named:
        raise ValueError(f"{archive.name} is not a toolchain archive")
    if not re.fullmatch(r"[1-9][0-9]*", revision):
        raise ValueError("the revision must be a positive number")
    tag = f"llvm-toolchain-{named[1]}-{revision}"
    digest = sha256(archive)
    checksum = archive.with_name(archive.name + ".sha256")
    if checksum.read_text().split() != [digest, archive.name]:
        raise ValueError(f"{checksum.name} is not the checksum of {archive.name}")
    if pinned and pinned[:2] == (archive.name, revision) and pinned[2] != digest:
        raise ValueError(f"pystachy_toolchain.py pins SHA-256 {pinned[2]} for {tag}, and this build has {digest}: "
                         "publish it under the next revision, then pin that")

    def release(action: str, *arguments: str) -> str:
        result = run("release", action, *arguments, "--repo", repository)
        if result.returncode:
            # gh's output may hold authenticated diagnostics: name the command alone.
            raise RuntimeError(f"gh release {action} exited {result.returncode}")
        return result.stdout

    def stored() -> str:
        with tempfile.TemporaryDirectory() as directory:
            release("download", tag, "--pattern", archive.name, "--dir", directory)
            return sha256(Path(directory) / archive.name)

    with tempfile.TemporaryDirectory() as directory:
        notes = Path(directory) / "notes.md"
        notes.write_text(NOTES.format(release=named[1], name=archive.name, digest=digest,
                                      repository=repository, commit=commit))
        described = ("--title", f"LLVM toolchain {named[1]}-{revision}", "--notes-file", str(notes),
                     "--target", commit, "--latest=false")
        found = run("release", "view", tag, "--json", "isDraft", "--repo", repository)
        if found.returncode == 0:
            if not json.loads(found.stdout)["isDraft"]:
                if stored() != digest:
                    raise RuntimeError(f"{tag} is published with another archive: this one needs the next revision")
                return f"{tag} already holds {archive.name}"
        elif "release not found" in found.stderr:
            release("create", tag, "--draft", *described)
        else:
            raise RuntimeError(f"gh release view exited {found.returncode}")
        release("upload", tag, str(archive), str(checksum), "--clobber")
        if stored() != digest:
            raise RuntimeError(f"the draft of {tag} holds other bytes than {archive.name}: it stays a draft")
        release("edit", tag, "--draft=false", "--prerelease=false", *described)
    listed = json.loads(release("list", "--limit", "30", "--json", "tagName,isLatest"))
    if [entry["isLatest"] for entry in listed if entry["tagName"] == tag] != [False]:
        raise RuntimeError(f"{tag} is the latest release, or is not listed: make the newest stable Pystachy latest")
    return f"published {tag} with {archive.name}, SHA-256 {digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True, help="the commit that built the archive")
    parser.add_argument("--revision", required=True, help="the number that ends the release's name")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("invalid repository")
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("the commit must be a full hash")
    try:
        pinned = (pystachy_toolchain.MINIMAL_ARCHIVE + ".tar.xz", pystachy_toolchain.MINIMAL_REVISION,
                  pystachy_toolchain.MINIMAL_SHA256)
        print(publish(args.repository, args.commit, args.revision, args.archive, pinned=pinned))
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"llvm_toolchain_release.py: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
