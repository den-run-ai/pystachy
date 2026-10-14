"""Promote or repair latest pointers for an already published stable release.

This never changes versioned images, release assets, or tags. Authenticate gh and
docker first; GH_TOKEN is required for the GitHub reads.
"""

import argparse
import os
import re
import subprocess
import sys

from release_gate import get_json, should_promote


def command(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, check=True, timeout=600)
    return result.stdout.strip()


def promote(repository, version, image, token):
    prefix = f"repos/{repository}/"
    release = get_json(prefix + "releases/tags/" + version, token)
    if release.get("draft") or release.get("prerelease"):
        raise RuntimeError("Only a published stable release can advance latest")
    obj = get_json(prefix + "git/ref/tags/" + version, token)["object"]
    for _ in range(8):
        if obj["type"] != "tag":
            break
        obj = get_json(prefix + "git/tags/" + obj["sha"], token)["object"]
    if obj["type"] != "commit":
        raise RuntimeError("Release tag does not resolve to a commit")
    commit = obj["sha"]
    latest = get_json(prefix + "releases/latest", token, missing_ok=True)
    previous = latest["tag_name"] if latest else None
    # Equality is intentional: recover a failed Docker promotion even if GitHub
    # already regards this release as latest. Newer versions are never displaced.
    if previous != version and not should_promote(version, previous):
        print("A newer stable version is already latest; nothing to change")
        return False
    source = image + ":" + version
    command(["docker", "pull", source])
    revision = command(["docker", "image", "inspect", source, "--format",
                        '{{index .Config.Labels "org.opencontainers.image.revision"}}'])
    label = command(["docker", "image", "inspect", source, "--format",
                     '{{index .Config.Labels "org.opencontainers.image.version"}}'])
    if revision != commit or label != version:
        raise RuntimeError("Versioned Docker image does not match the published release tag")
    command(["docker", "tag", source, image + ":latest"])
    command(["docker", "push", image + ":latest"])
    command(["gh", "release", "edit", version, "--repo", repository, "--latest"])
    print(f"Promoted {version}: Docker and GitHub latest match commit {commit}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("invalid repository")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.version):
        parser.error("version must be a stable v-prefixed semantic version")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*", args.image):
        parser.error("image must be namespace/repository")
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        parser.error("GH_TOKEN is required")
    try:
        promote(args.repository, args.version, args.image, token)
    except subprocess.CalledProcessError as error:
        # Command output may contain authenticated client diagnostics. Report
        # only the executable and exit status, never response bodies or tokens.
        parser.exit(1, f"promotion: {error.cmd[0]} exited {error.returncode}; retry this command after resolving the failure\n")
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"promotion: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
