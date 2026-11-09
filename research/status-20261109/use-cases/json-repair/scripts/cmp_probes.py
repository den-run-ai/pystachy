import json, sys
sys.path.insert(0, sys.argv[1])  # tools dir for normalize/exact_equal
from json_repair_parity import normalize, exact_equal
meta = json.load(open(sys.argv[2]))
names = sys.argv[3::2]; files = sys.argv[4::2]
rows = {}
for name, f in zip(names, files):
    for line in open(f):
        r = json.loads(line); i = str(r.pop("id"))
        if "value" in r: r["value"] = normalize(r["value"])
        rows.setdefault(i, {})[name] = r
def show(v):
    if v is None: return "MISSING"
    if "error" in v: return f"{v['error']}: {v['message']}"
    def de(t):
        k = t[0]
        if k == "none": return None
        if k in ("bool",): return t[1]
        if k == "int": return int(t[1])
        if k == "float": return float.fromhex(t[1])
        if k == "str": return "".join(chr(c) for c in t[1])
        if k == "list": return [de(x) for x in t[1]]
        if k == "tuple": return tuple(de(x) for x in t[1])
        if k == "dict": return {de(a): de(b) for a, b in t[1]}
    return repr(de(v["value"]))
for i in sorted(rows, key=int):
    m = meta[i]; r = rows[i]
    vals = [r.get(n) for n in names]
    same = all(exact_equal(vals[0], v) for v in vals[1:])
    print(f"[{m['tag']}] {m['api']}({m['input']!r}, {m['flags']}) {'SAME' if same else 'DIFF'}")
    for n, v in zip(names, vals):
        print(f"    {n:8} {show(v)[:150]}")
