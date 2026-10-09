"""The runtime ABI between runtime.py, runtime.c and programs: every function that runtime.py
defines or declares (pys_* exports, `def f(...) -> T: ...` externs) must have one LLVM signature
everywhere it appears, in runtime.c's IR (clang) and in the IR of every program of the corpus.
llvm-link accepts a mismatch without a word (a bool would be i1 on one side and i64 on the
other), so this is checked here. Parameter attributes and names are ignored.

usage: python3 tools/rtabi.py [COMPILER]   (default ./pystachy; PYSTACHY_LLVM for clang)
"""
import concurrent.futures
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
COMP = (sys.argv[1] if len(sys.argv) > 1 else "./pystachy").split()
LLVM = os.environ.get("PYSTACHY_LLVM", "")
CLANG = os.path.join(LLVM, "clang") if LLVM else "clang"
SIG = re.compile(r"^(define|declare)\s+(?:dso_local\s+|internal\s+)?(\S+)\s+@([\w.]+)\((.*?)\)")


def sigs(ir):
    # name -> "ret(params)" for each function defined or declared in an IR text
    out = {}
    for line in ir.splitlines():
        m = SIG.match(line)
        if m:
            params = []
            for p in m.group(4).split(","):
                p = p.strip()
                if p and p != "...":
                    params.append(p.split()[0])  # the type; attributes and %names follow it
            out[m.group(3)] = f"{m.group(2)}({', '.join(params)})"
    return out


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="latin-1")
    return r.returncode, r.stdout, r.stderr


code, rt_ir, err = run(COMP + ["rt", "runtime.py"])
if code != 0:
    sys.exit(f"cannot compile runtime.py: {err.strip()}")
mine = {k: v for k, v in sigs(rt_ir).items() if k.startswith("pys_") or k in re.findall(r"^def (\w+)\(.*\) -> .*: \.\.\.$", open("runtime.py").read(), re.M)}
code, c_ir, err = run([CLANG, "-O0", "-S", "-emit-llvm", "runtime.c", "-o", "-"])
if code != 0:
    sys.exit(f"cannot compile runtime.c: {err.strip()}")
seen = {"runtime.c": sigs(c_ir)}
progs = [f for f in ["pystachy.py"] + sorted(glob.glob("tests/*.py") + glob.glob("tests/deviations/*.py") + glob.glob("bench/*.py") + glob.glob("tests/ir/*.py"))]


def program(f):
    env = dict(os.environ)
    if os.path.exists(f[:-3] + ".path"):
        env["PYSTACHY_PATH"] = open(f[:-3] + ".path").read().strip()
    r = subprocess.run(COMP + ["ir", f], capture_output=True, text=True, encoding="latin-1", env=env)
    return f, sigs(r.stdout) if r.returncode == 0 else {}


with concurrent.futures.ThreadPoolExecutor(os.cpu_count() or 1) as ex:
    for f, s in ex.map(program, progs):
        seen[f] = s
bad = 0
uses = 0
for name, want in sorted(mine.items()):
    for where, s in seen.items():
        if name in s:
            uses += 1
            if s[name] != want:
                bad += 1
                print(f"MISMATCH {name}: runtime.py {want}, {where} {s[name]}")
print(f"{len(mine)} functions of runtime.py, {uses} uses in runtime.c and {len(progs)} programs, {bad} mismatches")
sys.exit(1 if bad else 0)
