#!/usr/bin/env python3
"""manifest.py DIR [OUT.json]: every entry under DIR (files: mode, size, sha256; directories:
mode; symlinks: target), sorted, plus one digest of the whole listing. Scratch evidence tool for
the alpha.2 IR qualification: run before and after each corpus run to prove a compiler home or a
corpus tree did not change while it was used."""
import hashlib
import json
import os
import stat
import sys


def entries(root):
    rows = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(dirs + files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root)
            info = os.lstat(path)
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                rows[rel] = {"kind": "symlink", "target": os.readlink(path)}
            elif stat.S_ISDIR(info.st_mode):
                rows[rel] = {"kind": "dir", "mode": mode}
            elif stat.S_ISREG(info.st_mode):
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                rows[rel] = {"kind": "file", "mode": mode, "size": info.st_size, "sha256": h.hexdigest()}
            else:
                rows[rel] = {"kind": "special", "mode": mode}
    return rows


def main():
    root = sys.argv[1]
    rows = entries(root)
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    out = {"root": os.path.realpath(root), "entries": len(rows), "digest": digest, "rows": rows}
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as f:
            json.dump(out, f, sort_keys=True, indent=1)
            f.write("\n")
    print(f"{digest} {len(rows)} {os.path.realpath(root)}")


if __name__ == "__main__":
    main()
