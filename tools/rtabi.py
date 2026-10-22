"""The runtime ABI between runtime.py, runtime.c and programs: every function that runtime.py
defines or declares (pys_* exports, `def f(...) -> T: ...` externs) must have one LLVM signature
everywhere it appears, in runtime.c's IR (clang) and in the IR of every program of the corpus.
llvm-link accepts a mismatch without a word (a bool would be i1 on one side and i64 on the
other), so this is checked here. Attributes and parameter names are ignored. Each extern must be
a function runtime.c defines. Str's header layout must also agree in compiler-emitted literals,
runtime.c and the CPython glue; matching pointer signatures alone cannot catch a shifted payload.

usage: python3 tools/rtabi.py [COMPILER]   (default ./pystachy; PYSTACHY_LLVM for clang)
"""
import concurrent.futures
import glob
import os
import re
import subprocess
import sys
import tempfile

from strabi import STR_PROBE, str_literal_errors, str_offset_errors, str_offsets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.pystachy_compiler.specs import STR_HEADER_SIZE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
COMP = (sys.argv[1] if len(sys.argv) > 1 else "./pystachy").split()
LLVM = os.environ.get("PYSTACHY_LLVM", "")
CLANG = os.path.join(LLVM, "clang") if LLVM else "clang"
SIG = re.compile(r"^(define|declare)\s+(.*?)\s*@([\w.]+)\((.*?)\)")


def sigs(ir):
    # name -> "ret(params)" for each function defined or declared in an IR text. The return type
    # is the last word before the name: linkage and return attributes (zeroext, noalias, ...) come first
    out = {}
    for line in ir.splitlines():
        m = SIG.match(line)
        if m:
            params = []
            for p in m.group(4).split(","):
                p = p.strip()
                if p and p != "...":
                    params.append(p.split()[0])  # the type; attributes and %names follow it
            out[m.group(3)] = f"{m.group(2).split()[-1]}({', '.join(params)})"
    return out


def str_layout(ir):
    m = re.search(r"^%struct\.Str = type \{(.*)\}$", ir, re.M)
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def literal_str_layouts(ir):
    return {re.sub(r"\s+", "", re.sub(r"\[\d+ x i8\]", "[0 x i8]", m))
            for m in re.findall(r"^@[sb]\.\d+ = private unnamed_addr global \{([^{}]+)\}", ir, re.M)}


# what clang writes for a C bool or char return, and for an allocator's
assert sigs("declare zeroext i1 @f(i64 noundef)\ndefine dso_local noalias nonnull ptr @g(i64 noundef %0) #0 {") == {"f": "i1(i64)", "g": "ptr(i64)"}
assert str_layout("%struct.Str = type { i64, i64, i64, [0 x i8] }") == "i64,i64,i64,[0xi8]"
assert literal_str_layouts('@s.0 = private unnamed_addr global {i64, i64, i64, [2 x i8]} {i64 1}') == {"i64,i64,i64,[0xi8]"}


def run(cmd, source=None):
    r = subprocess.run(cmd, input=source, capture_output=True, text=True, encoding="latin-1")
    return r.returncode, r.stdout, r.stderr


def compile_c(src, flags=()):
    return run([CLANG, "-O0", "-S", "-emit-llvm", "-x", "c", "-", "-I", ROOT, "-o", "-", *flags],
               f'#include "{src}"\n' + STR_PROBE)


code, rt_ir, err = run(COMP + ["rt", "runtime.py"])
if code != 0:
    sys.exit(f"cannot compile runtime.py: {err.strip()}")
externs = re.findall(r"^def (\w+)\(.*\) -> .*: \.\.\.$", open("runtime.py").read(), re.M)
mine = {k: v for k, v in sigs(rt_ir).items() if k.startswith("pys_") or k in externs}
code, c_ir, err = compile_c("runtime.c")
if code != 0:
    sys.exit(f"cannot compile runtime.c: {err.strip()}")
seen = {"runtime.c": sigs(c_ir)}
progs = [f for f in ["pystachy.py"] + sorted(glob.glob("tests/programs/*/*.py") + glob.glob("tests/deviations/*.py") + glob.glob("bench/*.py") + glob.glob("bench/pyperformance/*.py") + glob.glob("tests/ir/*.py"))]


def program(f):
    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="pystachy-rtabi-") as temporary:
        if os.path.exists(f[:-3] + ".path"):
            env["PYSTACHY_PATH"] = subprocess.check_output(
                ["sh", "tests/prepare_path.sh", f, temporary], text=True).rstrip("\n")
        r = subprocess.run(COMP + ["ir", f], capture_output=True, text=True, encoding="latin-1", env=env)
    return f, sigs(r.stdout) if r.returncode == 0 else {}


with concurrent.futures.ThreadPoolExecutor(os.cpu_count() or 1) as ex:
    for f, s in ex.map(program, progs):
        seen[f] = s
bad = 0
uses = 0
layout = str_layout(c_ir)
if not layout or literal_str_layouts(rt_ir) != {layout}:
    bad += 1
    print(f"MISMATCH Str layout: runtime.c {layout!r}, compiler literals {sorted(literal_str_layouts(rt_ir))}")
for error in str_offset_errors(str_offsets(c_ir), STR_HEADER_SIZE) + str_literal_errors(rt_ir):
    bad += 1
    print(f"MISMATCH {error}")
for name in externs:
    if not re.search(rf"^define .*@{name}\(", c_ir, re.M):
        bad += 1
        print(f"MISSING {name}: runtime.py declares it, runtime.c does not define it")
for name, want in sorted(mine.items()):
    for where, s in seen.items():
        if name in s:
            uses += 1
            if s[name] != want:
                bad += 1
                print(f"MISMATCH {name}: runtime.py {want}, {where} {s[name]}")
# the FFI's C glue (pyext.c, both ABIs; pyembed.c) declares the runtime.c functions it calls by hand
glue = 0
for src, flags in [("pyext.c", []), ("pyext.c", ["-DPYX_ABI3T"]), ("pyembed.c", [])]:
    code, g_ir, err = compile_c(src, flags)
    if code != 0:
        sys.exit(f"cannot compile {src}: {err.strip()}")
    if str_layout(g_ir) != layout:
        bad += 1
        print(f"MISMATCH Str layout: {src} {' '.join(flags)} {str_layout(g_ir)!r}, runtime.c {layout!r}")
    for error in str_offset_errors(str_offsets(g_ir), STR_HEADER_SIZE):
        bad += 1
        print(f"MISMATCH {src} {' '.join(flags)} {error}")
    rc = seen["runtime.c"]
    for name, got in sigs(g_ir).items():
        if name.startswith("pys_") and re.search(rf"^declare .*@{name}\(", g_ir, re.M):
            glue += 1
            if name not in rc or rc[name] != got:
                bad += 1
                print(f"MISMATCH {name}: {src} {' '.join(flags)} {got}, runtime.c {rc.get(name, 'none')}")
print(f"{glue} runtime calls of the FFI's C glue (pyext.c, both ABIs; pyembed.c) checked against runtime.c")
print(f"{len(mine)} functions of runtime.py, {uses} uses in runtime.c and {len(progs)} programs, {bad} mismatches")
sys.exit(1 if bad else 0)
