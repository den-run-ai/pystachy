"""Recompute the blocked-package tables of #171 (section 4) from packages.json.

python3 research/ports/tables.py [research/ports/packages.json]

A blocker counts when it is on the package's headline path and no small edit works around it
("hard"). A package is unblocked by a set of milestones when all its hard blockers are in it.
"""
import collections
import json
import os
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "packages.json")
P = json.load(open(path))


def milestone(roadmap):
    r = (roadmap or "").strip()
    if r.startswith("hub:"):
        return "M6"  # a standard-library hub
    m = re.match(r"(M\d)", r)
    return m.group(1) if m else "other"


def hard(rec):
    bs = [b for b in rec["blockers"] if isinstance(b, dict) and b.get("on_core_path", True)]
    h = {milestone(b.get("roadmap")) for b in bs if not b.get("small_edit_workaround", False)}
    return h or {milestone(b.get("roadmap")) for b in bs}


blocked = {k: v for k, v in P.items() if v["status"] == "blocked"}
need = {k: hard(v) for k, v in blocked.items()}
kinds = collections.Counter(v["kind"] for v in blocked.values())
print(f"{len(P)} probed, {len(blocked)} blocked ({kinds['pypi']} PyPI, {kinds['stdlib']} stdlib)")
print("\nblocked packages with a hard blocker in each milestone:")
for m, n in collections.Counter(m for h in need.values() for m in h).most_common():
    print(f"  {m:6} {n}")
print("\nunblocked by:")
steps = [("M1-M3", {"M1", "M2", "M3"}), ("+ M4", {"M4"}), ("+ M5, M6", {"M5", "M6"}), ("+ M7", {"M7"})]
done = set()
for name, ms in steps:
    done |= ms
    print(f"  {name:22} {sum(1 for h in need.values() if h <= done)}")
rest = {"M1", "M2", "M3", "M5", "M6", "M7"}
print(f"  {'all of M1-M7 but M4':22} {sum(1 for h in need.values() if h <= rest)}")

# What the hard M4 blockers are, by keyword on their description
cats = [("JSON- or TOML-like documents, mixed containers", r"json|toml|yaml|document|mixed|heterogen|any value|values of any|arbitrary (python )?(objects|values)|dict\[str, any\]|list\[any\]|nested"),
        ("getattr/setattr with computed names", r"getattr|setattr|hasattr|__dict__|vars\(|dynamic attribute|locals\(|globals\("),
        ("object() sentinels", r"sentinel|object\(\)"),
        ("isinstance over unions", r"union|isinstance|type dispatch|duck|either")]
c = collections.Counter()
for v in blocked.values():
    for b in v["blockers"]:
        if isinstance(b, dict) and milestone(b.get("roadmap")) == "M4" and b.get("on_core_path", True) \
                and not b.get("small_edit_workaround", False):
            t = b["feature"].lower()
            c[next((name for name, pat in cats if re.search(pat, t)), "other")] += 1
print(f"\nthe {sum(c.values())} hard M4 blockers:")
for name, n in c.most_common():
    print(f"  {n:3}  {name}")
