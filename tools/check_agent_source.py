"""Check the pinned AskMe example bytes, optionally against an AskMe checkout.

Each example directory names its source commit and file hashes in UPSTREAM.json.
With a checkout, every pinned file is also compared with that commit's bytes
(``git show COMMIT:PATH``), or with the checkout's working tree when the commit
is not present there.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXAMPLES = ("agent", "askme")


def upstream_bytes(checkout, commit, source_path):
    """The pinned commit's file, else the working tree's, else None."""
    shown = subprocess.run(["git", "-C", str(checkout), "show", f"{commit}:{source_path}"],
                           capture_output=True)
    if shown.returncode == 0:
        return shown.stdout
    path = checkout / source_path
    return path.read_bytes() if path.is_file() else None


def check(folder, upstream):
    manifest = json.loads((folder / "UPSTREAM.json").read_text())
    failures = []
    for item in manifest["files"]:
        label = f"{folder.name}/{item['path']}"
        local = folder / item["path"]
        if not local.is_file():
            failures.append(label + ": missing")
            continue
        if hashlib.sha256(local.read_bytes()).hexdigest() != item["sha256"]:
            failures.append(label + ": differs from pinned source hash")
        if upstream is not None:
            source = upstream_bytes(upstream, manifest["commit"], item["source_path"])
            if source is None:
                failures.append(label + ": not found in the AskMe checkout")
            elif local.read_bytes() != source:
                failures.append(label + ": differs from AskMe checkout")
    return manifest, failures


def main() -> int:
    if len(sys.argv) > 2:
        print("usage: check_agent_source.py [ASKME_CHECKOUT]", file=sys.stderr)
        return 2
    upstream = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    examples = Path(__file__).resolve().parents[1] / "examples"
    failures = []
    lines = []
    for name in EXAMPLES:
        manifest, found = check(examples / name, upstream)
        failures += found
        lines.append(f"{len(manifest['files'])} pinned AskMe files verified at {manifest['commit']}"
                     f" (examples/{name})")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
