"""Check the pinned AskMe example bytes, optionally against its checkout."""

import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    folder = Path(__file__).resolve().parents[1] / "examples" / "agent"
    manifest = json.loads((folder / "UPSTREAM.json").read_text())
    upstream = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    if len(sys.argv) > 2:
        print("usage: check_agent_source.py [ASKME_CHECKOUT]", file=sys.stderr)
        return 2
    failures = []
    for item in manifest["files"]:
        local = folder / item["path"]
        if hashlib.sha256(local.read_bytes()).hexdigest() != item["sha256"]:
            failures.append(item["path"] + ": differs from pinned source hash")
        if upstream is not None and local.read_bytes() != (upstream / item["source_path"]).read_bytes():
            failures.append(item["path"] + ": differs from AskMe checkout")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(str(len(manifest["files"])) + " pinned AskMe files verified at " + manifest["commit"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
