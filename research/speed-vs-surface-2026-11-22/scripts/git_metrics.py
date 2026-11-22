"""Per-commit source-size and test-corpus metrics for every first-parent commit of main (git only).

usage: python3 git_metrics.py REPO REF OUT.json
"""
import json
import subprocess
import sys
from collections import defaultdict


def classify(path):
    """Bucket a tracked path; None means not counted."""
    if path == "pystachy.py" or (path.startswith("src/") and path.endswith(".py")):
        return "compiler"
    if path in ("runtime.c", "runtime.py", "pyembed.c", "pyext.c", "lljit.c") or path.startswith(("ryu/", "mpz/")) and path.endswith((".c", ".h")):
        return "runtime"
    if path.startswith("lib/") and path.endswith(".py"):
        return "library"
    return None


def corpus_kind(path):
    """Differential cases (.py with a recorded .out/.err sibling are counted from the .py)."""
    if not path.endswith(".py") or not path.startswith("tests/"):
        return None
    parts = path.split("/")
    if parts[1] == "errors":
        return "errors"
    if parts[1] == "deviations":
        return "deviations"
    if parts[1] == "programs" or len(parts) == 2:
        return "programs"
    return None


def main():
    repo, ref, out = sys.argv[1:]
    git = ["git", "-C", repo]
    commits = subprocess.run(git + ["log", "--first-parent", "--reverse", "--format=%H %ct %s", ref],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    tags = {}
    for line in subprocess.run(git + ["tag", "-l", "--format=%(refname:short) %(*objectname)%(objectname)"],
                               capture_output=True, text=True, check=True).stdout.splitlines():
        name, sha = line.split()
        sha = subprocess.run(git + ["rev-list", "-n1", name], capture_output=True, text=True).stdout.strip()
        tags.setdefault(sha, []).append(name)
    lines_cache = {}
    cat = subprocess.Popen(git + ["cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def blob_lines(sha):
        if sha not in lines_cache:
            cat.stdin.write(sha.encode() + b"\n")
            cat.stdin.flush()
            header = cat.stdout.readline().split()
            size = int(header[2])
            data = cat.stdout.read(size)
            cat.stdout.read(1)
            lines_cache[sha] = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
        return lines_cache[sha]

    rows = []
    for line in commits:
        sha, ts, subject = line.split(" ", 2)
        tree = subprocess.run(git + ["ls-tree", "-r", sha], capture_output=True, text=True, check=True).stdout
        loc = defaultdict(int)
        files = defaultdict(int)
        corpus = defaultdict(int)
        sidecars = set()
        pys = []
        for entry in tree.splitlines():
            meta, path = entry.split("\t", 1)
            _, kind, blob = meta.split()
            if kind != "blob":
                continue
            b = classify(path)
            if b:
                loc[b] += blob_lines(blob)
                files[b] += 1
            if path.startswith("tests/") and path.endswith((".out", ".err")):
                sidecars.add(path.rsplit(".", 1)[0])
            k = corpus_kind(path)
            if k:
                pys.append((k, path))
        for k, path in pys:
            stem = path[:-3]
            # a case is a .py with a recorded expectation (.out/.err) or an error/deviation case
            if k == "programs" and stem not in sidecars:
                continue
            corpus[k] += 1
        rows.append({"sha": sha, "time": int(ts), "subject": subject, "tags": tags.get(sha, []),
                     "loc": dict(loc), "files": dict(files), "corpus": dict(corpus)})
    cat.stdin.close()
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=0)
    first, last = rows[0], rows[-1]
    print(len(rows), "commits;", "first", first["loc"], first["corpus"], "last", last["loc"], last["corpus"])


if __name__ == "__main__":
    main()
