"""Gate PyPI publication of an existing, verified GitHub release."""

import argparse
from email.parser import BytesParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import urllib.parse
import zipfile

from packaging.version import Version

from release_gate import get_json, workflow_states


def package_version(version: str) -> str:
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", version):
        raise ValueError("version must be a v-prefixed semantic version")
    return str(Version(version[1:]))


def git(source: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(source), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError("Source must contain the release tag and full origin/main history")
    return result.stdout.strip()


def source_commit(source: Path, version: str) -> str:
    if (source / "VERSION").read_text().strip() != version:
        raise RuntimeError("Release tag must match source/VERSION")
    if git(source, "rev-parse", "--is-shallow-repository") != "false":
        raise RuntimeError("Source checkout requires fetch-depth: 0")
    commit = git(source, "rev-parse", "--verify", "HEAD^{commit}")
    if git(source, "rev-parse", "--verify", f"refs/tags/{version}^{{commit}}") != commit:
        raise RuntimeError("Source HEAD does not match the release tag")
    git(source, "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("Source checkout must be clean")
    return commit


def published_release(repository: str, version: str, commit: str, token: str) -> None:
    prefix = f"repos/{repository}/"
    tag = urllib.parse.quote(version, safe="")
    release = get_json(prefix + "releases/tags/" + tag, token, missing_ok=True)
    if not release or release.get("draft") is not False or not release.get("published_at"):
        raise RuntimeError("A published, non-draft GitHub release is required")
    if release.get("tag_name") != version or release.get("target_commitish") != commit:
        raise RuntimeError("GitHub release tag and target must identify the exact source commit")
    ref = get_json(prefix + "git/ref/tags/" + tag, token, missing_ok=True)
    obj = ref["object"] if ref else {}
    for _ in range(8):
        if obj.get("type") != "tag":
            break
        obj = get_json(prefix + "git/tags/" + obj["sha"], token)["object"]
    if obj.get("type") != "commit" or obj.get("sha") != commit:
        raise RuntimeError("Published release tag does not resolve to the source commit")


def verified_workflows(repository: str, commit: str, token: str) -> None:
    runs = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"head_sha": commit, "branch": "main", "event": "push",
                                        "per_page": 100, "page": page})
        data = get_json(f"repos/{repository}/actions/runs?{query}", token)
        if data.get("total_count", 0) > 1000:
            raise RuntimeError("Workflow results exceed GitHub's searchable limit")
        batch = data["workflow_runs"]
        runs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    states = workflow_states(runs, commit)
    blocked = [f"{name}: {state}" for name, state in states.items() if state != "success"]
    if blocked:
        raise RuntimeError("Source commit lacks successful main-push workflows: " + ", ".join(blocked))


def check_metadata(data: bytes, version: str) -> None:
    metadata = BytesParser().parsebytes(data)
    if metadata.get_all("Name") != ["pystachy"] or metadata.get_all("Version") != [version]:
        raise RuntimeError("Distribution metadata must identify pystachy " + version)


def check_paths(names: list[str]) -> None:
    if len(set(names)) != len(names) or any(PurePosixPath(name).is_absolute() or
                                          ".." in PurePosixPath(name).parts or "\\" in name
                                          for name in names):
        raise RuntimeError("Distribution contains unsafe or duplicate archive paths")


def audit_dist(directory: Path, version: str) -> None:
    """Accept only the source archive and universal wheel built for this version."""
    stem = "pystachy-" + version
    expected = {stem + ".tar.gz", stem + "-py3-none-any.whl"}
    # uv build creates this hidden bookkeeping file; it is not an upload input.
    actual = {path.name for path in directory.iterdir() if path.name != ".gitignore"}
    if actual != expected or any(not (directory / name).is_file() or
                                 (directory / name).is_symlink() for name in expected):
        raise RuntimeError("Distribution directory must contain exactly " + ", ".join(sorted(expected)))
    with zipfile.ZipFile(directory / (stem + "-py3-none-any.whl")) as wheel:
        check_paths(wheel.namelist())
        metadata = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if metadata != [stem + ".dist-info/METADATA"]:
            raise RuntimeError("Wheel must contain exactly its expected package metadata")
        check_metadata(wheel.read(metadata[0]), version)
    with tarfile.open(directory / (stem + ".tar.gz"), "r:gz") as sdist:
        check_paths(sdist.getnames())
        if any(not (member.isfile() or member.isdir()) for member in sdist.getmembers()):
            raise RuntimeError("Source archive contains a link or special file")
        metadata = [member for member in sdist.getmembers() if member.name == stem + "/PKG-INFO"]
        if len(metadata) != 1 or not metadata[0].isfile():
            raise RuntimeError("Source archive must contain exactly its expected package metadata")
        with sdist.extractfile(metadata[0]) as stream:
            check_metadata(stream.read(), version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("invalid repository")
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        parser.error("GH_TOKEN is required")
    try:
        version = package_version(args.version)
        commit = source_commit(args.source, args.version)
        published_release(args.repository, args.version, commit, token)
        verified_workflows(args.repository, commit, token)
        if args.dist:
            audit_dist(args.dist, version)
        outputs = {"package_version": version, "commit": commit}
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                output.writelines(f"{name}={value}\n" for name, value in outputs.items())
        else:
            print(json.dumps(outputs))
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"PyPI release gate: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
