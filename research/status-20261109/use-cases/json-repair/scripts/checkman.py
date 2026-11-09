import hashlib, json, sys
from pathlib import Path
man = json.load(open(sys.argv[1]))
root = Path(sys.argv[2])
bad = 0
for rel, h in man["source_sha256"].items():
    p = root / rel.replace("src/", "")
    got = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"
    if got != h:
        bad += 1
        print("DIFF", rel, got[:12], h[:12])
print("checked", len(man["source_sha256"]), "mismatches", bad)
