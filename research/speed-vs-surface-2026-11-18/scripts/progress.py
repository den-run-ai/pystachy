"""Compare two method sweeps: methods gained and lost, by test file and by the old first error's group.

usage: python3 progress.py OLD_METHODS.json NEW_METHODS.json OUT.json
Groups follow groups.py (first matching row wins); the old first error explains what blocked each
newly passing method before. Status codes: pass (match or match-python-int), differs, timeout, rejected.
"""
import collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import category, group  # noqa: E402
import importlib.util
spec = importlib.util.spec_from_file_location("groups_mod", Path(__file__).resolve().parent / "groups.py")
GROUPS = None
src = (Path(__file__).resolve().parent / "groups.py").read_text()
GROUPS = eval(src[src.index("GROUPS = [") + len("GROUPS = "):src.index("]\nrecs") + 1])

P = ("match", "match-python-int")


def state(r):
    s = r["status"]
    return "pass" if s in P else "rejected" if s == "compile-error" else s


def need(detail):
    for kind, name, pat in GROUPS:
        if re.search(pat, detail or ""):
            return f"{kind}: {name}"
    return f"unassigned ({category(detail or '')})"


old, new, out = sys.argv[1:]
a = {(r["file"], r["test"]): r for r in json.load(open(old))["records"]}
b = {(r["file"], r["test"]): r for r in json.load(open(new))["records"]}
gained, lost, moved = [], [], collections.Counter()
for k, rb in b.items():
    ra = a[k]
    sa, sb = state(ra), state(rb)
    if sa != sb:
        moved[(sa, sb)] += 1
    if sb == "pass" and sa != "pass":
        gained.append((k, sa, ra.get("detail", "")))
    if sa == "pass" and sb != "pass":
        lost.append((k, sb, rb.get("detail", "")))
by_file = collections.Counter(k[0] for k, _, _ in gained)
by_need = collections.Counter(need(d) if s == "rejected" else s for _, s, d in gained)
lang = sum(group(k[0]) == "language" for k, _, _ in gained)
def short(d):
    d = re.sub(r"^[^ ]*\.py:(\d+:)? ", "", d or "")
    d = re.sub(r"'[^']*__[a-z0-9_]+'", "'...'", d)
    return re.sub(r" \((sys, os|available: ).*$", "", d)[:110]


old_errors = collections.Counter(short(d) for _, s, d in gained if s == "rejected")
res = {"old": old, "new": new,
       "pass_old": sum(state(r) == "pass" for r in a.values()), "pass_new": sum(state(r) == "pass" for r in b.values()),
       "gained": len(gained), "gained_language": lang, "lost": len(lost),
       "gained_by_file": by_file.most_common(), "gained_by_old_blocker": by_need.most_common(),
       "gained_old_first_errors": old_errors.most_common(25),
       "lost_detail": [[k[0], k[1], s, d[:200]] for k, s, d in lost],
       "transitions": [[x, y, n] for (x, y), n in moved.most_common()],
       "rejected_new_by_need": collections.Counter(need(r.get("detail", "")) for r in b.values()
                                                   if r["status"] == "compile-error").most_common()}
json.dump(res, open(out, "w"), indent=1)
print(f"pass {res['pass_old']} -> {res['pass_new']}: gained {len(gained)} ({lang} language), lost {len(lost)}")
print("gained by file:", by_file.most_common(15))
print("gained by old blocker:", by_need.most_common(12))
print("old first errors:", old_errors.most_common(8))
print("transitions:", moved.most_common(12))
for row in res["lost_detail"][:10]:
    print("lost:", row)
