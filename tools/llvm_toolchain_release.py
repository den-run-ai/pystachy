"""Publish built LLVM toolchain archives as the assets of their own GitHub release.

The release is llvm-toolchain-<LLVM release>-<revision> and holds one archive for each
architecture. It is not a Pystachy version, and it must never be the repository's latest release,
which names the newest stable Pystachy. The release is a draft until its archives have been read
back. A published one is not changed: the same archives pass, and others need the next revision.
Authenticate gh first (GH_TOKEN).
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ARCHIVE = re.compile(r"pystachy-llvm-([0-9]+\.[0-9]+\.[0-9]+)-linux-(?:x86_64|aarch64)\.tar\.xz")
NOTES = """\
The minimal LLVM {release} toolchain for Pystachy on Linux: `clang`, `opt`, `lli`, `llc`, `llvm-link` \
and `llvm-as` over one single-target `libLLVM`. This is not a Pystachy release.

{archives}

Built at {repository}@{commit} by `tools/llvm_toolchain.sh`: \
[contents, build and check](https://github.com/{repository}/blob/{commit}/docs/llvm-toolchain.md). \
LLVM's license and the terms of the third-party code in it are in each archive's `share/licenses`.
"""


def gh(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *arguments], capture_output=True, text=True, timeout=600)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def publish(repository: str, commit: str, revision: str, archives: list[Path], run=gh) -> str:
    """Publish the archives and return what was done; run stands in for gh in tests."""
    if not re.fullmatch(r"[1-9][0-9]*", revision):
        raise ValueError("the revision must be a positive number")
    releases = set()
    for archive in archives:
        named = ARCHIVE.fullmatch(archive.name)
        if not named:
            raise ValueError(f"{archive.name} is not a toolchain archive")
        releases.add(named[1])
    if len(releases) != 1 or len({archive.name for archive in archives}) != len(archives):
        raise ValueError("the archives must be of one LLVM release, one for each architecture")
    llvm = releases.pop()
    tag = f"llvm-toolchain-{llvm}-{revision}"
    digests = {}
    for archive in archives:
        digests[archive.name] = sha256(archive)
        checksum = archive.with_name(archive.name + ".sha256")
        if checksum.read_text().split() != [digests[archive.name], archive.name]:
            raise ValueError(f"{checksum.name} is not the checksum of {archive.name}")

    def release(action: str, *arguments: str) -> str:
        result = run("release", action, *arguments, "--repo", repository)
        if result.returncode:
            # gh's output may hold authenticated diagnostics: name the command alone.
            raise RuntimeError(f"gh release {action} exited {result.returncode}")
        return result.stdout

    def stored() -> dict:
        with tempfile.TemporaryDirectory() as directory:
            for name in digests:
                release("download", tag, "--pattern", name, "--dir", directory)
            return {name: sha256(Path(directory) / name) for name in digests}

    held = ", ".join(f"{name} (SHA-256 {digest})" for name, digest in digests.items())
    with tempfile.TemporaryDirectory() as directory:
        notes = Path(directory) / "notes.md"
        notes.write_text(NOTES.format(
            release=llvm, repository=repository, commit=commit,
            archives="\n".join(f"- `{name}`: SHA-256 `{digest}`" for name, digest in digests.items())))
        described = ("--title", f"LLVM toolchain {llvm}-{revision}", "--notes-file", str(notes),
                     "--target", commit, "--latest=false")
        found = run("release", "view", tag, "--json", "isDraft", "--repo", repository)
        if found.returncode == 0:
            if not json.loads(found.stdout)["isDraft"]:
                if stored() != digests:
                    raise RuntimeError(f"{tag} is published with other archives: these need the next revision")
                return f"{tag} already holds {held}"
        elif "release not found" in found.stderr:
            release("create", tag, "--draft", *described)
        else:
            raise RuntimeError(f"gh release view exited {found.returncode}")
        files = [str(file) for archive in archives for file in (archive, archive.with_name(archive.name + ".sha256"))]
        release("upload", tag, *files, "--clobber")
        if stored() != digests:
            raise RuntimeError(f"the draft of {tag} holds other bytes than were uploaded: it stays a draft")
        release("edit", tag, "--draft=false", "--prerelease=false", *described)
    listed = json.loads(release("list", "--limit", "30", "--json", "tagName,isLatest"))
    if [entry["isLatest"] for entry in listed if entry["tagName"] == tag] != [False]:
        raise RuntimeError(f"{tag} is the latest release, or is not listed: make the newest stable Pystachy latest")
    return f"published {tag} with {held}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True, help="the commit that built the archives")
    parser.add_argument("--revision", required=True, help="the number that ends the release's name")
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("invalid repository")
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("the commit must be a full hash")
    try:
        print(publish(args.repository, args.commit, args.revision, args.archives))
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"llvm_toolchain_release.py: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
