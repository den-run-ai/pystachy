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
    the lists and dicts in it), and N if the C function is noreturn;
  - it has rL or wL if it reads or writes the memory of a list parameter (S of a list.* entry,
    or list[...]), rD or wD a dict's (S of dict.*, dict[...]) and rF or wF a file's (S of
    file.*, file), which loads and stores through addresses derived from the parameter show:
    through getelementptr, load (the list's items array, an item), phi, select and casts,
    the locals they are stored in, and the parameters of the runtime functions they are passed
    to (from clang -O1, whose SSA form leaves few locals; a C library function other than
    READS_ONLY counts as both, and user code as neither: that is U);
  - it has I if its call graph, outside the end of the program (R) and the allocator (A),
    reads or writes a mutable static of the runtime other than NO_STATE's or calls a C library
    function other than PURE_C's (I/O, the process, the time). The passes rely on these: an
    op with wL or wD may change a list or a dict, and an op whose letters are at most R
    computes its result from its arguments alone (Gen.canon).
    More letters than runtime.c shows are allowed (an entry may be conservative); -v lists
    those of R, N, A, I and of the letters derived from parameters.
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
# the end of the program (R and N stand for it; running out of memory, oom, for A) and the
# allocator (A), which I does not look into
END = RAISES | {"oom"}
ALLOC = {"gc_slow", "pys_alloc", "pys_alloc_atomic"}
# C library functions that use no state but the memory their arguments point to
PURE_C = set("""sqrt sin cos tan asin acos atan sinh cosh tanh exp log log2 log10 log1p expm1 exp2 cbrt fmod
    atan2 pow ldexp frexp atoi memcmp bcmp memchr memmem strlen strchr strstr strcmp strncasecmp snprintf
    sprintf vsnprintf strtod __isoc23_strtol __isoc23_strtoll __ctype_b_loc __ctype_tolower_loc
    __errno_location""".split())
# and those that only read the memory their pointer arguments point to
READS_ONLY = set("""memcmp bcmp memchr memmem strlen strchr strstr strcmp strncasecmp strtod __isoc23_strtol
    __isoc23_strtoll fwrite fputs fprintf snprintf sprintf vsnprintf write""".split())
# runtime statics that keep no state from one call to the next: the cache of one-character
# strings (immutable, made on first use) and the scratch buffers of round(x, n)
NO_STATE = {"ch1", "pys_round_n.b", "pys_round_n.o"}
# the parameter types whose memory the letters rL wL, rD wD and rF wF are about, by entry prefix
# for S (the receiver)
OWNER = {"list.": "L", "dict.": "D", "file.": "F"}


def load_compiler():
    spec = importlib.util.spec_from_file_location("pystachy", os.path.join(ROOT, "pystachy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def llvm_ir(src, name, opt="-O0"):
    # the LLVM IR clang compiles C source file src to, unoptimized (or at level opt)
    out = subprocess.run([TOOL + "clang", "-S", "-emit-llvm", opt, "-o", "-", src], capture_output=True, text=True)
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


def split_top(s):
    # s split at the commas outside (), [] and {}
    parts, depth, cur = [], 0, []
    for c in s:
        if c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        depth += c in "([{"
        depth -= c in ")]}"
        cur.append(c)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def ssa(operand):
    # the SSA value an operand ("ptr noundef %3") names, or None (a constant, a global)
    m = re.search(r"(%[\w.]+)\s*$", operand)
    return m.group(1) if m else None


def instruction(ins):
    # (kind, result, operands) of an instruction, for the kinds params() follows, or None: call
    # (callee, arguments), store (value, address), ret (value), load (address), gep (base),
    # alloca, rmw (address), and phi (its values; also select's, and a cast's operand)
    m = re.match(r"(%[\w.]+) = (?:(?:tail|musttail|notail) )?(\w+)", ins)
    dest, op = (m.group(1), m.group(2)) if m else (None, re.sub(r"^(?:(?:tail|musttail|notail) )", "", ins).split()[0])
    if op == "call":
        rest = ins[ins.find("call ") + 5 :]
        c = re.search(r"([@%][\w.]+)\(", rest)
        i = j = c.end()
        depth = 1
        while depth:
            depth += (rest[j] == "(") - (rest[j] == ")")
            j += 1
        return ("call", dest, (c.group(1)[1:], [ssa(a) for a in split_top(rest[i : j - 1])]))
    if op == "store":
        ps = split_top(ins[6:])
        return ("store", None, (ssa(ps[0]), ssa(ps[1])))
    if op == "ret":
        return ("ret", None, (ssa(ins[4:]),))
    if op in ("atomicrmw", "cmpxchg"):
        return ("rmw", dest, (ssa(split_top(ins[ins.find(op) + len(op) :])[0]),))
    if dest is None:
        return None
    body = ins[ins.find(op, len(dest)) + len(op) :].strip()
    if op == "load":
        return ("load", dest, (ssa(split_top(body)[1]),))
    if op == "getelementptr":
        return ("gep", dest, (ssa(split_top(body)[1]),))
    if op == "alloca":
        return ("alloca", dest, ())
    if op == "phi":
        return ("phi", dest, tuple(v.strip() for v in re.findall(r"\[\s*([^,\]]+),", body)))
    if op == "select":
        ps = split_top(body)
        return ("phi", dest, (ssa(ps[1]), ssa(ps[2])))
    if op in ("inttoptr", "ptrtoint", "bitcast", "freeze", "addrspacecast"):
        return ("phi", dest, (ssa(body[: body.find(" to ")]),))
    return None


def params(ll):
    # name -> for each parameter of each function ll defines, whether the function reads (r)
    # and writes (w) memory reachable from it, as [r, w, ret] (ret: it may return an address
    # derived from it), or None for a parameter that is no ptr or i64
    fns = {}
    cur = None
    for line in ll.split("\n"):
        m = re.match(r"define [^@]*@([\w.]+)\((.*)\)[^(]*\{$", line)
        if m:
            cur = ([ssa(p) if p.startswith(("ptr", "i64")) else None for p in split_top(m.group(2))], [])
            fns[m.group(1)] = cur
        elif line == "}":
            cur = None
        elif cur is not None and line.startswith("  "):
            x = instruction(line.strip())
            if x is not None:
                cur[1].append(x)
    eff = {f: [None if p is None else [False, False, False] for p in fns[f][0]] for f in fns}
    more = True
    while more:
        more = False
        for f in fns:
            for k, p in enumerate(fns[f][0]):
                if p is not None:
                    got = derived(fns, eff, f, p)
                    if got != eff[f][k]:
                        eff[f][k] = got
                        more = True
    return eff


def derived(fns, eff, f, p):
    # [r, w, ret] of function f for parameter p: the values derived from p (D), and the locals
    # (allocas) a derived value was stored in, whose loads are derived too
    body = fns[f][1]
    D = {p}
    loc = {}  # an alloca, or an address in one -> that alloca
    held = set()
    r = w = ret = False
    more = True
    while more:
        more = False
        for kind, dest, ops in body:
            if kind == "alloca":
                loc[dest] = dest
            elif kind == "call":
                g, args = ops
                hit = [i for i, a in enumerate(args) if a in D or loc.get(a) in held]
                if not hit or g in USER:
                    continue
                if g.startswith("llvm."):
                    if g.startswith(("llvm.memcpy", "llvm.memmove", "llvm.memset")):
                        w = w or args[0] in D
                        r = r or (args[1] in D and not g.startswith("llvm.memset"))
                elif g in eff:
                    for i in hit:
                        if i < len(eff[g]) and eff[g][i] is not None:
                            r = r or eff[g][i][0]
                            w = w or eff[g][i][1]
                            if eff[g][i][2] and dest is not None and dest not in D:
                                D.add(dest)
                                more = True
                else:
                    r = True
                    w = w or g not in READS_ONLY
            elif kind == "store":
                w = w or ops[1] in D
                if ops[0] in D and ops[1] in loc and loc[ops[1]] not in held:
                    held.add(loc[ops[1]])
                    more = True
            elif kind == "ret":
                ret = ret or ops[0] in D
            elif kind == "rmw":
                r = r or ops[0] in D
                w = w or ops[0] in D
            elif dest not in D:
                if kind == "load":
                    new = ops[0] in D or loc.get(ops[0]) in held
                    r = r or ops[0] in D
                elif kind == "gep":
                    new = ops[0] in D
                    if ops[0] in loc and dest not in loc:
                        loc[dest] = loc[ops[0]]
                        more = True
                else:
                    new = any(v in D for v in ops)
                if new:
                    D.add(dest)
                    more = True
    return [r, w, ret]


def state(ll):
    # name -> the mutable statics of the runtime (and of the C library: stdout) that each
    # function ll defines reads or writes: the address of a load or a store, the base of a
    # getelementptr, or an argument of a call, but not a stored value nor an operand of icmp,
    # select, phi or ret (which only compare or pass the address: pys_std, the sort's sentinel)
    mutable = set(re.findall(r"^@([\w.]+) = (?:[a-z_]+ )*global ", ll, re.M))
    used = {}
    cur = None
    for line in ll.split("\n"):
        m = re.match(r"define .*?@([\w.]+)\(", line)
        if m:
            cur = used.setdefault(m.group(1), set())
        elif line == "}":
            cur = None
        elif cur is not None:
            gs = set(re.findall(r"\bload [^,]+, ptr @([\w.]+)", line))
            gs.update(re.findall(r"getelementptr (?:inbounds )?(?:\(\s*)?[^,]+, ptr @([\w.]+)", line))
            if line.lstrip().startswith("store "):
                a = split_top(line.lstrip()[6:])[1]
                gs.update(re.findall(r"^ptr @([\w.]+)$", a))
            if re.search(r"\bcall\b", line):
                gs.update(re.findall(r"ptr (?:noundef |nonnull |align \d+ )*@([\w.]+)", line[line.find("(", line.find("@")) :]))
            cur.update(gs & mutable)
    return used


def uses_state(fns, used, f):
    # does f's call graph, outside the end of the program and the allocator, use state (I)?
    seen = set()
    todo = [f]
    while todo:
        g = todo.pop()
        if g in seen or g in END or g in ALLOC or g in USER or g not in fns:
            continue
        seen.add(g)
        if g not in used:
            if not g.startswith("llvm.") and g not in PURE_C:
                return True  # (a C library function)
        elif used[g] - NO_STATE:
            return True
        else:
            todo.extend(fns[g][3])
    return False


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
    ll = llvm_ir(os.path.join(ROOT, "runtime.c"), "runtime.c")
    fns = functions(ll)
    used = state(ll)
    eff = params(llvm_ir(os.path.join(ROOT, "runtime.c"), "runtime.c", "-O1"))
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
        if uses_state(fns, used, sym):
            derived.append("I")
        for i, p in enumerate(pys.rtsig(k)[1:]):
            o = OWNER.get(k[: k.find(".") + 1], "") if p == "S" else "L" if p.startswith("list[") else "D" if p.startswith("dict[") else "F" if p == "file" else ""
            if o and sym in eff and i < len(eff[sym]) and eff[sym][i] is not None:
                derived.extend((["r" + o] if eff[sym][i][0] else []) + (["w" + o] if eff[sym][i][1] else []))
        for x in derived:
            if x not in letters and "U" not in letters and not (x == "U" and "U?" in letters):
                bad.append(f"{k}: {sym} has effect {x} in runtime.c, which RUNTIME leaves out")
        for x in ("R", "N", "A", "I", "rL", "wL", "rD", "wD", "rF", "wF"):
            if x in letters and x not in derived:
                note.append(f"{k}: {x}, which runtime.c does not show")
    for b in bad:
        print(b)
    if verbose:
        for n in note:
            print("note:", n)
    print(f"{len(rt)} RUNTIME entries: " + (f"{len(bad)} problems" if bad else "signatures, coverage and effects agree with runtime.c"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
