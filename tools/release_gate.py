"""Require successful main CI on the exact release commit and a new version."""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REQUIRED_WORKFLOWS = ("CI", "Installation", "Lint")


def should_promote(version: str, latest: str | None) -> bool:
    """An older stable release must never move either registry's latest pointer."""
    current = re.fullmatch(r"v([0-9]+)\.([0-9]+)\.([0-9]+)", version)
    previous = re.fullmatch(r"v([0-9]+)\.([0-9]+)\.([0-9]+)", latest or "")
    if not current:
        return False
    if latest is None:
        return True
    if not previous:
        raise RuntimeError("Latest release is not a recognized stable version; promote manually")
    return tuple(map(int, current.groups())) > tuple(map(int, previous.groups()))


def workflow_states(runs: list[dict], commit: str) -> dict[str, str]:
    """Select the newest push run for each workflow; stale successes do not count."""
    newest = {}
    for run in runs:
        name = run.get("name")
        if (name not in REQUIRED_WORKFLOWS or run.get("head_sha") != commit
                or run.get("head_branch") != "main" or run.get("event") != "push"):
            continue
        if name not in newest or run["id"] > newest[name]["id"]:
            newest[name] = run
    return {
        name: (newest[name].get("conclusion") or "pending")
        if name in newest and newest[name].get("status") == "completed" else "pending"
        for name in REQUIRED_WORKFLOWS
    }


def get_json(path: str, token: str, *, missing_ok: bool = False):
    request = urllib.request.Request(
        "https://api.github.com/" + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        # Do not print response/request bodies or authorization headers.
        raise RuntimeError(f"GitHub API returned HTTP {error.code}") from None


def validate_version(repository: str, commit: str, version: str, token: str) -> None:
    prefix = f"repos/{repository}/"
    release = get_json(prefix + "releases/tags/" + version, token, missing_ok=True)
    if release and not release.get("draft"):
        raise RuntimeError("This version is already published; choose a new version")
    ref = get_json(prefix + "git/ref/tags/" + version, token, missing_ok=True)
    if ref:
        obj = ref["object"]
        for _ in range(8):
            if obj["type"] != "tag":
                break
            obj = get_json(prefix + "git/tags/" + obj["sha"], token)["object"]
        if obj["type"] != "commit" or obj["sha"] != commit:
            raise RuntimeError("The release tag points to a different commit")
    elif release and release.get("target_commitish") != commit:
        raise RuntimeError("The existing draft targets a different commit; choose a new version")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("invalid repository")
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("commit must be a full SHA")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", args.version):
        parser.error("version must be a v-prefixed semantic version")
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        parser.error("GH_TOKEN is required")
    try:
        validate_version(args.repository, args.commit, args.version, token)
        deadline = time.monotonic() + max(0, args.wait_seconds)
        query = urllib.parse.urlencode({"head_sha": args.commit, "branch": "main",
                                        "event": "push", "per_page": 100})
        while True:
            data = get_json(f"repos/{args.repository}/actions/runs?{query}", token)
            states = workflow_states(data["workflow_runs"], args.commit)
            print(", ".join(f"{name}: {state}" for name, state in states.items()), flush=True)
            failed = {name: state for name, state in states.items() if state not in ("pending", "success")}
            if failed:
                raise RuntimeError("Release commit has a failed or cancelled verification workflow")
            if all(state == "success" for state in states.values()):
                return 0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Release commit is missing successful CI, Installation, or Lint")
            time.sleep(min(20, remaining))
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f"release gate: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
