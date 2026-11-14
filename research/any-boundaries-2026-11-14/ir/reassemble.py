"""Restore the audited archives, checking every part and the complete byte stream."""
from pathlib import Path
import hashlib
import json
import os
import tempfile


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "archive-parts.json").read_text())
    for archive in manifest["archives"]:
        target = root / archive["file"]
        if target.exists():
            if target.stat().st_size != archive["size"] or digest(target) != archive["sha256"]:
                raise ValueError(f"Existing archive differs: {target}")
            print(f"Verified existing {target.name}")
            continue
        temporary = None
        try:
            h, size = hashlib.sha256(), 0
            with tempfile.NamedTemporaryFile(dir=root, prefix="reassemble-", delete=False) as output:
                temporary = Path(output.name)
                for part in archive["parts"]:
                    data = (root / part["file"]).read_bytes()
                    if len(data) != part["size"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
                        raise ValueError(f"Archive part differs: {part['file']}")
                    output.write(data)
                    h.update(data)
                    size += len(data)
            if size != archive["size"] or h.hexdigest() != archive["sha256"]:
                raise ValueError(f"Combined archive differs: {archive['file']}")
            os.replace(temporary, target)
            temporary = None
            print(f"Restored and verified {target.name}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
