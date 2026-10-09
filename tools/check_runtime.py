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
A function that runtime.py defines instead (docs/runtime-in-subset.md) is checked from the IR the
compiler builds for runtime.py, in this process:
  - signatures: its definition has the entry's types (runtime.c may only declare it, with them);
  - effects: R if it raises (a raise statement, or a call of a function that may raise), A if it
    allocates, U if it runs user code and I if it does I/O, through the runtime functions it
    calls (their entries, or runtime.c's call graph for one runtime.py declares). The subset's
    implicit checks (overflow, indexes, a zero divisor: check ops, and the operations of
    IMPLICIT) do not count as R: they are runtime.c's unchecked arithmetic and indexing, and they
    fire only on a bug of runtime.py;
  - recursion: no function of runtime.py reaches itself through runtime.c. The compiler rejects
    an operation that lowers to the function it is in; a cycle through runtime.c (pys_format_str
    formatting with a nested spec, which calls runtime.c's pys_format, which calls pys_format_str)
    would recurse without end where nothing in the source shows a call.
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
NO_USER = {"dict.getitem", "dict.pop", "dict.pop_default"}
RAISES = {"pys_fail", "pys_raise", "oserr", "kbint_exit"}
USER = {"pys_obj_eq", "pys_obj_cmp", "pys_obj_repr"}
# the functions that walk a value by its descriptor (its static type), reading the lists and dicts in it
BY_DESC = {"eqv", "opv", "repr"}
# the operations whose only raise is one of the subset's implicit checks, in runtime.py as in a
# program: an index out of range, a zero divisor, a negative shift count, a float that does not
# fit an int, a square root's domain. In runtime.py, as a check op's, it fires only on a bug.
IMPLICIT = {"str.get", "list.get", "list.set", "floordiv", "mod", "shl", "shr", "f2i", "m.sqrt"}


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
    # name -> (result, params, noreturn, callees, "define" or "declare") of every function ll
    # defines or declares
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
            fns[m.group(3)] = (result, params, noreturn, set(), m.group(1))
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


def runtime_py(pys):
    # the IR the compiler builds for runtime.py: (its LLVM text, symbol -> the ops of each function
    # it compiles, as (op, text immediate) pairs, captured before they are lowered). The ops of
    # its cold blocks, which raise what its implicit checks find, are left out
    path = os.path.join(ROOT, "runtime.py")
    ops = {}

    class Capture(pys.Gen):
        def lower(self, fn):
            cold = set(fn.cold.values())
            ops[fn.f.ll[1:]] = [(i.op, i.s) for b in fn.blocks if b.label not in cold for i in b.code]
            pys.Gen.lower(self, fn)

    sys.setrecursionlimit(pys.MAXNEST * 40)  # (as the compiler's main does)
    pys.SRC = path
    with open(path, encoding="latin-1") as f:
        src = f.read()
    g = Capture()
    g.rtmode = True
    pys.MODULES["_rt"] = True
    ir = g.program(pys.Loader([]).program(path, src))
    del pys.MODULES["_rt"]
    return ir, ops


def cycle(graph, start, inner):
    # a path from start back to start that goes through a node of inner, or None; graph: node ->
    # its successors
    def path(a, b):
        # a shortest path from a to b, as a list of nodes, or None
        prev = {a: None}
        todo = [a]
        while todo:
            n = todo.pop(0)
            for m in sorted(graph.get(n, ())):
                if m == b:
                    out = [b]
                    while n is not None:
                        out.append(n)
                        n = prev[n]
                    return out[::-1]
                if m not in prev:
                    prev[m] = n
                    todo.append(m)
        return None

    for y in sorted(inner):
        there = path(start, y)
        back = path(y, start) if there else None
        if there and back:
            return there + back[1:]
    return None


# a cycle through a node of inner: found, the shortest way there and back; none without one
assert cycle({"p": {"c"}, "c": {"p"}}, "p", {"c"}) == ["p", "c", "p"]
assert cycle({"p": {"p", "c"}, "c": set()}, "p", {"c"}) is None
assert cycle({"p": {"q"}, "q": {"c"}, "c": {"d"}, "d": {"q"}}, "p", {"c"}) is None


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
            f.write("#define _GNU_SOURCE\n#include <math.h>\n#include <stdlib.h>\n#include <stdio.h>\n#include <string.h>\n")
            f.write("".join(f"void *probe{i} = (void *)&{s};\n" for i, s in enumerate(libc)))
        cfns = functions(llvm_ir(probe, "a probe of the C library"))
        intrinsics = [pys.runtime_decl(k) for k in rt if pys.rtsym(k).startswith("llvm.")]
        mod = os.path.join(tmp, "intrinsics.ll")
        with open(mod, "w") as f:
            f.write("\n".join(intrinsics) + "\n")
        out = subprocess.run([TOOL + "llvm-as", "-o", os.devnull, mod], capture_output=True, text=True)
        if out.returncode != 0:
            bad.append(f"llvm-as rejects the intrinsics' declarations: {out.stderr.strip()}")
    rpy_ir, rpy_ops = runtime_py(pys)
    pyfns = {n: v for n, v in functions(rpy_ir).items() if v[4] == "define"}
    # signatures
    for k in rt:
        sym = pys.rtsym(k)
        if sym.startswith("llvm."):
            continue
        want = pys.runtime_decl(k)
        if sym in pyfns:
            # runtime.py's: runtime.c may declare it (and call it), with the same types
            have = pyfns[sym]
            got = f"declare {have[0]} @{sym}({', '.join(have[1])})"
            if want != got:
                bad.append(f"{k}: RUNTIME declares {want[8:]}, runtime.py defines {got[8:]}")
            if sym in fns and fns[sym][4] == "define":
                bad.append(f"{k}: both runtime.c and runtime.py define {sym}")
            elif sym in fns and f"declare {fns[sym][0]} @{sym}({', '.join(fns[sym][1])})" != want:
                bad.append(f"{k}: RUNTIME declares {want[8:]}, runtime.c declares {sym} as {fns[sym][0]}({', '.join(fns[sym][1])})")
            continue
        have = fns.get(sym) or cfns.get(sym)
        if have is None:
            bad.append(f"{k}: neither runtime.c nor runtime.py has a function {sym}")
            continue
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
    # (and what the compiler calls by its symbol, such as runtime mode's memchr)
    named.update(re.findall(r"""self\.rt\(\s*["']([\w.]+)["']""", src))
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
    # effects and recursion of runtime.py's functions, from their ops (see the docstring)
    letters = {}  # runtime.py's function -> the effect letters derived (R A U I)
    for f, ops in rpy_ops.items():
        m = set()
        for op, x in ops:
            if op == "raise":
                m.add("R")
            elif op == "rt" and pys.rtsym(x) not in rpy_ops:
                e = rt[x]
                m.update(y for y in e[e.find("|") + 1 : e.rfind("|")].replace("U?", "U").split() if y in ("A", "U", "I") or (y == "R" and x not in IMPLICIT))
            elif op == "call" and x[1:] not in rpy_ops:
                # one of runtime.c's functions, which runtime.py declares
                if reaches(fns, x[1:], RAISES, {"gc_slow"}):
                    m.add("R")
                if reaches(fns, x[1:], {"gc_slow"}, set()):
                    m.add("A")
                if reaches(fns, x[1:], USER, set()):
                    m.add("U")
        letters[f] = m
    more = True
    while more:
        more = False
        for f, ops in rpy_ops.items():
            for op, x in ops:
                g = pys.rtsym(x) if op == "rt" else x[1:] if op == "call" else ""
                if g in letters and g != f and not letters[g] <= letters[f]:
                    letters[f] |= letters[g]
                    more = True
    for k in rt:
        sym = pys.rtsym(k)
        if sym not in rpy_ops:
            continue
        e = rt[k]
        have = e[e.find("|") + 1 : e.rfind("|")].split()
        for x in sorted(letters[sym]):
            if x not in have and not (x == "U" and "U?" in have):
                bad.append(f"{k}: runtime.py's {sym} has effect {x}, which RUNTIME leaves out")
        if "N" in have:
            bad.append(f"{k}: RUNTIME says N, but runtime.py's {sym} returns")
        for x in ("R", "A"):
            if x in have and x not in letters[sym]:
                note.append(f"{k}: {x}, which runtime.py's code does not show")
    graph = {n: v[3] for n, v in fns.items() if v[4] == "define"}
    for f, ops in rpy_ops.items():
        graph[f] = {pys.rtsym(x) if op == "rt" else x[1:] for op, x in ops if op in ("rt", "call")}
    inner = {n for n in graph if n not in rpy_ops}
    for f in sorted(rpy_ops):
        c = cycle(graph, f, inner)
        if c:
            bad.append(f"runtime.py's {f} reaches itself through runtime.c ({' -> '.join(c)}): it would recurse without end")
    for b in bad:
        print(b)
    if verbose:
        for n in note:
            print("note:", n)
    print(f"{len(rt)} RUNTIME entries: " + (f"{len(bad)} problems" if bad else f"signatures, coverage and effects agree with runtime.c and runtime.py ({len(rpy_ops)} functions, none of which reaches itself through runtime.c)"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
