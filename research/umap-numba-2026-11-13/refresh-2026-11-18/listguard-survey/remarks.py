"""Summarize optimization-record YAML files: per function, the loop vectorizer's outcome
(vectorized with width/interleave, or the missed/analysis reasons) and LICM/unroll counts.
usage: remarks.py FILE.yaml..."""
import re
import sys

for path in sys.argv[1:]:
    text = open(path).read()
    docs = text.split("\n--- ")
    rows = []
    for d in docs:
        kind = re.match(r"^-* ?!(\w+)", d.strip())
        pas = re.search(r"Pass:\s+(\S+)", d)
        name = re.search(r"Name:\s+(\S+)", d)
        fn = re.search(r"Function:\s+(\S+)", d)
        if not (kind and pas and name and fn):
            continue
        strs = re.findall(r"- (?:String|ExtraString|Reason|VectorizationFactor|InterleaveCount|Cost|Width|Count):\s+'?([^'\n]*)'?", d)
        msg = "".join(strs).strip()
        if pas.group(1) in ("loop-vectorize", "slp-vectorizer", "loop-unroll"):
            rows.append(f"  {kind.group(1):9} {pas.group(1):15} {fn.group(1)[:28]:28} {name.group(1)}: {msg[:150]}")
    print(path.split("/")[-1])
    seen = set()
    for r in rows:
        if r not in seen:
            seen.add(r)
            print(r)
