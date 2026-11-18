"""Compact per-method history: one row per qualified CPython test method, one code per sampled commit.

usage: python3 export_matrix.py COMMITS.txt OUT.csv.gz OUT-head-errors.csv.gz
Codes: P passes, I passes with promoting ints, D compiles but differs, T timeout, and for a
compile rejection the cause of its first error: L library, S syntax, Y typing, M dynamic model, O other.
"""
import csv
import gzip
import json
import sys
from pathlib import Path

from classify import category, group, strip

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
CODE = {"match": "P", "match-python-int": "I", "differs": "D", "timeout": "T"}
CAT = {"library": "L", "syntax": "S", "typing": "Y", "dynamic": "M", "other": "O"}


def main():
    commits_file, out, head_out = sys.argv[1:]
    labels = sorted(line.split()[0] for line in open(commits_file) if line.strip())
    status = {}
    head = None
    for lab in labels:
        f = S / "results" / f"methods-{lab}.json"
        if not f.exists():
            continue
        head = lab
        for r in json.load(open(f))["records"]:
            code = CODE.get(r["status"]) or CAT[category(r.get("detail", ""))]
            status.setdefault((r["file"], r["test"]), {})[lab] = code
    labels = [lab for lab in labels if (S / "results" / f"methods-{lab}.json").exists()]
    with gzip.open(out, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "test", "group"] + labels)
        for (file, test), codes in sorted(status.items()):
            w.writerow([file, test, group(file)] + [codes.get(lab, "") for lab in labels])
    with gzip.open(head_out, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "test", "status", "cause", "first_error"])
        for r in json.load(open(S / "results" / f"methods-{head}.json"))["records"]:
            ce = r["status"] == "compile-error"
            w.writerow([r["file"], r["test"], r["status"], category(r.get("detail", "")) if ce else "",
                        strip(r.get("detail", ""))[:300] if r["status"] != "match" else ""])
    print(len(status), "methods x", len(labels), "commits; head", head)


if __name__ == "__main__":
    main()
