"""What the library-blocked methods hit when CPython's own pure-Python stdlib is on PYSTACHY_PATH (HEAD only).

usage: python3 overlay.py SHIPPED.json OVERLAY.json OUT.json [DYNAMIC-ANY.json]
"""
import collections
import json
import re
import sys

from classify import category

LABEL = {
    "library": "a module or name still missing",
    "dynamic": "dynamic model (generic bases, redefinitions, class-body statements)",
    "typing": "static typing (type not inferred)",
    "syntax": "unimplemented syntax",
    "other": "other",
}


def main():
    shipped, overlay, out = sys.argv[1:4]
    dynany = sys.argv[4] if len(sys.argv) > 4 else None
    a = {(r["file"], r["test"]): r for r in json.load(open(shipped))["records"]}
    b = {(r["file"], r["test"]): r for r in json.load(open(overlay))["records"]}
    passing = lambda r: r["status"] in ("match", "match-python-int")
    rows = [{"order": 1, "group": "all methods", "outcome": "passing with Pystachy's own library",
             "methods": sum(1 for r in a.values() if passing(r))},
            {"order": 2, "group": "all methods", "outcome": "passing with CPython's pure-Python stdlib added",
             "methods": sum(1 for r in b.values() if passing(r))}]
    if dynany:
        c = json.load(open(dynany))["records"]
        rows.append({"order": 2.5, "group": "all methods", "outcome": "passing with every test opted in to dynamic Any",
                     "methods": sum(1 for r in c if passing(r))})
    lib = [k for k, r in a.items() if r["status"] == "compile-error" and category(r.get("detail", "")) == "library"]
    rows.append({"order": 3, "group": "blocked by a missing library piece", "outcome": "total", "methods": len(lib)})
    rows.append({"order": 4, "group": "blocked by a missing library piece", "outcome": "pass once CPython's stdlib is added",
                 "methods": sum(1 for k in lib if passing(b[k]))})
    inside, intest = collections.Counter(), collections.Counter()
    for k in lib:
        r = b[k]
        if r["status"] != "compile-error":
            continue
        m = re.match(r"^([^ ]+\.py): ", r.get("detail", ""))
        in_test = bool(m and "__" in m.group(1))
        (intest if in_test else inside)[category(r.get("detail", ""))] += 1
    order = 5
    for cat in LABEL:
        if inside[cat]:
            rows.append({"order": order, "group": "now rejected inside CPython's library code", "outcome": LABEL[cat],
                         "methods": inside[cat]})
            order += 1
    for cat in LABEL:
        if intest[cat]:
            rows.append({"order": order, "group": "still rejected in the test itself", "outcome": LABEL[cat],
                         "methods": intest[cat]})
            order += 1
    json.dump(rows, open(out, "w"), indent=0)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
