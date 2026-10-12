"""Census of each port against the upstream modules it keeps: the cross-check of #171, section 2.

python3 research/ports/census_ports.py SDISTS
SDISTS holds the unpacked sdists, NAME-VERSION/ each, as `pip download --no-deps --no-binary
:all: NAME==VERSION` gives them. A port is read from ports/ when it is there, else from its
origin/claude/port-* branch. tools/census.py runs as it is, with --json; tools/port_edits.py
(#182) gives the same comparison for one port at a time.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

PORTS = [  # (port directory, PyPI name, version)
    ("convertdate", "convertdate", "2.5.1"), ("jdcal", "jdcal", "1.4.1"), ("ordered_set", "ordered-set", "4.1.0"),
    ("pyaes", "pyaes", "1.6.1"), ("pyfiglet", "pyfiglet", "1.0.4"), ("pylev", "pylev", "1.4.0"),
    ("qrcode", "qrcode", "8.2"), ("roman", "roman", "5.2"), ("sgp4", "sgp4", "2.27"),
    ("snowballstemmer", "snowballstemmer", "3.1.1"), ("sortedcontainers", "sortedcontainers", "2.4.0"),
    ("sqids", "sqids", "0.5.2"), ("tomli_w", "tomli-w", "1.2.0"), ("wcwidth", "wcwidth", "0.9.2"),
]


def git(*a):
    return subprocess.run(("git",) + a, capture_output=True, text=True, check=True).stdout


def upstream_file(root, pkg, rel):
    want = [os.path.join(pkg, rel)] + ([pkg + ".py"] if rel == "__init__.py" else [])
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in ("tests", "test", "build", "docs"))
        for w in want:
            if os.path.isfile(os.path.join(dp, w)):
                return os.path.join(dp, w)
    return None


# census blockers by the milestone that would make the edit unnecessary (#5's milestones)
MILESTONE = {
    "M2 classes": "unannotated method, inherit, class_body_stmt, class_decorator, deco:property, deco:staticmethod, "
                  "deco:classmethod, dyn:staticmethod, dyn:classmethod, dyn:property, dyn:super",
    "M3 functions as values": "first_class_fn, lambda, nested_def, decorator, star_params, star_call, dyn:map, "
                              "dyn:filter, nonlocal",
    "M4 dynamic values": "dyn:isinstance, dyn:type, none_default, dyn:id, dyn:getattr, dyn:setattr, dyn:hasattr, "
                         "dyn:object, dyn:issubclass, dyn:callable, dyn:hash",
    "M5 exceptions": "try, raise_custom",
    "M6 stdlib (import_other also counts a package's own relative imports)": "import_other",
    "M7 long tail": "yield, set, dyn:set, dyn:frozenset, bytes, dyn:bytes, str_format, percent_format, slice_step, "
                    "dyn:iter, dyn:next, dyn:slice, dyn:tuple, starred, dictcomp, nested_comp, del_name, async, walrus, "
                    "match, complex, bigint_literal, matmul",
    "M1 runtime gaps": "dyn:hex, dyn:oct, dyn:bin",
}
OF = {b: m for m, bs in MILESTONE.items() for b in bs.split(", ")}
removed = {}
sdists = sys.argv[1]


def census(root):
    """Blocker counts over root, "unannotated" split by the kind of unit."""
    js = root + ".json"
    subprocess.run([sys.executable, "-I", "tools/census.py", root, "--json", js], check=True, stdout=subprocess.DEVNULL)
    counts = {}
    for r in json.load(open(js)):
        for k, n in r.get("blockers", {}).items():
            k = k + " " + r["kind"] if k == "unannotated" else k
            counts[k] = counts.get(k, 0) + n
    return counts


for pdir, name, version in PORTS:
    ref = "HEAD" if os.path.isdir(os.path.join("ports", pdir)) else "origin/claude/port-" + name
    files = [f for f in git("ls-tree", "-r", "--name-only", ref, "ports/" + pdir).split() if f.endswith(".py")]
    root = next((os.path.join(sdists, d) for d in os.listdir(sdists)
                 if d.lower().replace("_", "-") == f"{name}-{version}".lower()), None)
    tmp = tempfile.mkdtemp()
    kept, only_port = [], []
    for f in files:
        rel = f.split("/", 2)[2]
        up = upstream_file(root, pdir, rel) if root else None
        if up is None:
            only_port.append(rel)
            continue
        kept.append(rel)
        for side, text in (("upstream", open(up, encoding="utf-8").read()), ("port", git("show", ref + ":" + f))):
            dest = os.path.join(tmp, side, pdir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w", encoding="utf-8").write(text)
    print(f"== {name} {version} ({ref}): {len(kept)} modules kept" + (f"; only in the port: {', '.join(only_port)}" if only_port else ""))
    up, po = census(os.path.join(tmp, "upstream", pdir)), census(os.path.join(tmp, "port", pdir))
    shutil.rmtree(tmp)
    for k in sorted(set(up) | set(po), key=lambda k: (po.get(k, 0) - up.get(k, 0), k)):
        if up.get(k, 0) != po.get(k, 0):
            print(f"  {up.get(k, 0):6} -> {po.get(k, 0):<4} {k}")
        if k != "unannotated function" and up.get(k, 0) > po.get(k, 0):
            m = OF.get(k, "unmapped: " + k)
            removed[m] = removed.get(m, 0) + up[k] - po.get(k, 0)
n = sum(removed.values())
print(f"== census blockers the 14 ports' edits removed: {n}")
for m, k in sorted(removed.items(), key=lambda x: -x[1]):
    print(f"{k:5}  {100 * k / n:4.1f}%  {m}")
