"""Check the compiler's RUNTIME table (pystachy.py) against runtime.c.

usage: python3 tools/check_runtime.py [-v]
RUNTIME gives every runtime function the compiler declares its signature and its effect letters
(docs/typed-ir.md 3.7); the compiler builds each declare line from it, and an rt() call that
disagrees with its entry is an internal error. This tool checks the table itself:
  - signatures: each entry's declare line has the result and parameter types of the function
    clang compiles runtime.c to (LLVM IR at -O0); a C library function (fabs) is taken from a
    file that includes <math.h>, and llvm-as checks the LLVM intrinsics (llvm.*);
  - coverage: every runtime function pystachy.py names (METHODS, CALLS, IRT, FRT, the "pys_..."
    strings of its source, the file attributes Gen.expr names as pys_file_<attribute> and the
    __pys_repr_enter/leave builtins) has an entry, and every entry is named;
  - effects: every letter is one of the compiler's FX, or U?; an entry has R if the function's
    C call graph reaches pys_fail, pys_raise, oserr or kbint_exit (not counting the allocator's
    MemoryError: that is A), A if it reaches the allocator's slow path (gc_slow), U or U? if it
    reaches pys_obj_eq, pys_obj_cmp or pys_obj_repr (user code), rL and rD if it has a #
    parameter and reaches eqv, opv or repr (which walk a value of any type by its descriptor:
    the lists and dicts in it), and N if the C function is noreturn. More letters than the call
    graph shows are allowed (an entry may be conservative); -v lists them.
The exit status is 1 if a check fails. Clang and llvm-as come from PATH, or PYSTACHY_LLVM.
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LLVM = os.environ.get("PYSTACHY_LLVM", "")
TOOL = (LLVM.rstrip("/") + "/") if LLVM else ""
# functions whose call graph reaches user code only through a KeyError's repr of the key: dict
# keys are int or str, whose repr never calls user code
NO_USER = {"dict.getitem", "dict.entry", "dict.pop", "dict.pop_default"}
RAISES = {"pys_fail", "pys_raise", "oserr", "kbint_exit"}
USER = {"pys_obj_eq", "pys_obj_cmp", "pys_obj_repr"}
# the functions that walk a value by its descriptor (its static type), reading the lists and dicts in it
BY_DESC = {"eqv", "opv", "repr"}


def load_compiler():
    spec = importlib.util.spec_from_file_location("pystachy", os.path.join(ROOT, "pystachy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def llvm_ir(src, name):
    # the LLVM IR clang compiles C source file src to, unoptimized
    out = subprocess.run([TOOL + "clang", "-S", "-emit-llvm", "-O0", "-o", "-", src], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"check_runtime: clang cannot compile {name}:\n{out.stderr}")
    return out.stdout


def functions(ll):
    # name -> (result, params, noreturn, callees) of every function ll defines or declares
    groups = {}
    for m in re.finditer(r"^attributes #(\d+) = \{(.*)\}$", ll, re.M):
        groups[m.group(1)] = m.group(2)
    fns = {}
    cur = None
    for line in ll.split("\n"):
        m = re.match(r"(define|declare) (.*?)@([\w.]+)\((.*)\)(.*?)(\{)?$", line)
        if m:
            words = m.group(2).split()
            result = words[-1] if words else ""
            params = []
            depth = 0
            part = ""
            for c in m.group(4) + ",":
                if c == "," and depth == 0:
                    if part.strip() and part.strip() != "...":
                        params.append(part.split()[0])
                    part = ""
                    continue
                depth += c in "({["
                depth -= c in ")}]"
                part += c
            attrs = m.group(5)
            noreturn = "noreturn" in attrs.split() or any(groups.get(g, "").split().count("noreturn") for g in re.findall(r"#(\d+)", attrs))
            fns[m.group(3)] = (result, params, noreturn, set())
            cur = m.group(3) if m.group(1) == "define" else None
            continue
        if line == "}":
            cur = None
        elif cur is not None:
            fns[cur][3].update(re.findall(r"@([\w.]+)", line))
    return fns


def reaches(fns, f, targets, skip):
    # does f's call graph reach one of targets, not going through the functions in skip?
    seen = set()
    todo = [f]
    while todo:
        g = todo.pop()
        if g in seen or g in skip:
            continue
        if g in targets:
            return True
        seen.add(g)
        if g in fns:
            todo.extend(fns[g][3])
    return False


def main():
    verbose = "-v" in sys.argv[1:]
    pys = load_compiler()
    rt = pys.RUNTIME
    bad = []
    note = []
    fns = functions(llvm_ir(os.path.join(ROOT, "runtime.c"), "runtime.c"))
    with tempfile.TemporaryDirectory() as tmp:
        libc = [pys.rtsym(k) for k in rt if not pys.rtsym(k).startswith(("pys_", "llvm."))]
        probe = os.path.join(tmp, "probe.c")
        with open(probe, "w") as f:
            f.write("#include <math.h>\n#include <stdlib.h>\n#include <stdio.h>\n")
            f.write("".join(f"void *probe{i} = (void *)&{s};\n" for i, s in enumerate(libc)))
        cfns = functions(llvm_ir(probe, "a probe of the C library"))
        intrinsics = [pys.runtime_decl(k) for k in rt if pys.rtsym(k).startswith("llvm.")]
        mod = os.path.join(tmp, "intrinsics.ll")
        with open(mod, "w") as f:
            f.write("\n".join(intrinsics) + "\n")
        out = subprocess.run([TOOL + "llvm-as", "-o", os.devnull, mod], capture_output=True, text=True)
        if out.returncode != 0:
            bad.append(f"llvm-as rejects the intrinsics' declarations: {out.stderr.strip()}")
    # signatures
    for k in rt:
        sym = pys.rtsym(k)
        if sym.startswith("llvm."):
            continue
        have = fns.get(sym) or cfns.get(sym)
        if have is None:
            bad.append(f"{k}: runtime.c has no function {sym}")
            continue
        want = pys.runtime_decl(k)
        got = f"declare {have[0]} @{sym}({', '.join(have[1])})"
        if want != got:
            bad.append(f"{k}: RUNTIME declares {want[8:]}, runtime.c defines {got[8:]}")
    # coverage
    src = open(os.path.join(ROOT, "pystachy.py")).read()
    named = set()
    for key in pys.METHODS:
        named.add("pys_" + key.replace(".", "_"))
    for spec in pys.CALLS.values():
        named.add(spec.split(":")[0])
    named.update(pys.IRT.values())
    named.update(pys.FRT.values())
    named.update(f"llvm.{op}.with.overflow.i64" for op in pys.CHECKED.values())
    # (not the pys_obj_ functions, which the program defines, nor the names of the compiler's
    # own builtins, __pys_*, of which Gen.builtin calls two by their names without __)
    named.update(s for s in re.findall(r"(?<!_)pys_[a-z0-9_]*[a-z0-9](?![\w{])", src) if not s.startswith("pys_obj_"))
    named.update(["pys_repr_enter", "pys_repr_leave"])
    named.update(f"pys_file_{a}" for a in ("closed", "name", "mode"))
    named.add("llvm.frameaddress.p0")
    for s in sorted(named):
        if s not in pys.RTSYM:
            bad.append(f"{s}: pystachy.py names it, but RUNTIME has no entry for it")
    for s in sorted(pys.RTSYM):
        if s not in named:
            bad.append(f"{pys.RTSYM[s]}: RUNTIME's entry is for {s}, which pystachy.py never names")
    # effects
    for k in rt:
        sym = pys.rtsym(k)
        if sym not in fns:
            continue
        e = rt[k]
        letters = e[e.find("|") + 1 : e.rfind("|")].split()
        for x in letters:
            if x not in pys.FX and x != "U?":
                bad.append(f"{k}: {x} is no effect letter (FX)")
        derived = []
        if reaches(fns, sym, RAISES, {"gc_slow"}):
            derived.append("R")
        if fns[sym][2]:
            derived.append("N")
        if reaches(fns, sym, {"gc_slow"}, set()):
            derived.append("A")
        if reaches(fns, sym, USER, set()) and k not in NO_USER:
            derived.append("U")
        if "#" in pys.rtsig(k)[1:] and reaches(fns, sym, BY_DESC, set()):
            derived.extend(["rL", "rD"])
        for x in derived:
            if x not in letters and not (x == "U" and "U?" in letters):
                bad.append(f"{k}: {sym} has effect {x} in runtime.c, which RUNTIME leaves out")
        for x in ("R", "N", "A"):
            if x in letters and x not in derived:
                note.append(f"{k}: {x}, which the call graph does not show")
    for b in bad:
        print(b)
    if verbose:
        for n in note:
            print("note:", n)
    print(f"{len(rt)} RUNTIME entries: " + (f"{len(bad)} problems" if bad else "signatures, coverage and effects agree with runtime.c"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
