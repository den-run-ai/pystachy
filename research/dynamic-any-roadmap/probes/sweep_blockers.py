# usage: sweep_blockers.py BASE.json OPTIN.json OPTIN_LIBDIR : compares two tools/import_sweep.py results,
# without and with the comment in every module (optin_stdlib.py), after removing OPTIN_LIBDIR from paths
# and line numbers from locations (the comment moves every line down by one); prints the modules whose
# result differs and the modules of each kind of first blocker
import collections
import json
import re
import sys

base, optin = (json.load(open(p)) for p in sys.argv[1:3])
base, optin = base.get("results", base), optin.get("results", optin)
prefix = sys.argv[3].rstrip("/") + "/"


def norm(v):
    v = re.sub(r"\S*/", "", str(v).replace(prefix, ""))
    return re.sub(r":\d+", ":N", v)


def kind(v):
    v = str(v)
    if v == "OK":
        return "imports"
    if "missing module" in v or "is not a builtin module" in v:
        return "a module that CPython builds in is missing"
    if "cannot be used as a value" in v:
        return "a class used as a value"
    if "dict keys must be" in v:
        return "a dict keyed by builtin functions or types"
    if re.search(r"class \S+ is not supported|inheritance|base class|metaclass", v):
        return "a class feature (bases, enum, generic inheritance)"
    return "another language feature"


tried = [m for m in sorted(base) if "lib/ has" not in str(base[m])]
print(len(tried), "modules tried;", sum(base[m] == "OK" for m in tried), "import without the comment,",
      sum(optin.get(m) == "OK" for m in tried), "with it")
for m in tried:
    if norm(base[m]) != norm(optin.get(m)):
        print("differs:", m, "|", norm(base[m])[:160], "|", norm(optin.get(m))[:160])
for name, res in (("without the comment", base), ("with the comment", optin)):
    groups = collections.defaultdict(list)
    for m in tried:
        groups[kind(res.get(m))].append(m)
    print(f"\nfirst blockers {name}:")
    for k, ms in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(ms):4d}  {k}" + ("" if k == "imports" or name != "without the comment" else ": " + " ".join(ms)))
