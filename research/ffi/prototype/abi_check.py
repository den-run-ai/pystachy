# abi_check.py TOML SO MAXVER ENTRY: SO defines one dynamic symbol, ENTRY, and every Py* symbol it
# imports is in CPython's stable ABI (Misc/stable_abi.toml) added at MAXVER or before. Exit 1 if not.
# (Needs python3: it runs in the verify-py step. The Python-free stage checks only the export, with nm.)
import subprocess, sys, tomllib
toml, so, maxs, entry = sys.argv[1:5]
maxv = tuple(int(x) for x in maxs.split("."))
t = tomllib.load(open(toml, "rb"))
ok = {name: tuple(int(x) for x in v["added"].split(".")) for kind in ("function", "data") for name, v in t.get(kind, {}).items()}
def nm(flag):
    r = subprocess.run(["nm", "-D", flag, so], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"{so}: nm failed: {r.stderr.strip()}")
    return [l.split()[-1] for l in r.stdout.splitlines() if l.strip()]
defined, und = nm("--defined-only"), nm("--undefined-only")
syms = [s for s in und if s.startswith(("Py", "_Py"))]
bad = [s for s in syms if s not in ok or ok[s] > maxv]
if defined != [entry] or not syms or bad:
    sys.exit(f"{so}: defines {defined} (want [{entry}]); {len(syms)} Py symbols; not in the stable ABI <= {maxs}: {bad}")
print(f"{so.split('/')[-1]}: defines only {entry}; {len(syms)} Py symbols, all in the stable ABI <= {maxs}")
