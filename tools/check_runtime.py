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
A function that runtime.py defines instead (docs/runtime-in-subset.md) is checked from the IR the
compiler builds for runtime.py, in this process:
  - signatures: its definition has the entry's types (runtime.c may only declare it, with them);
    the compiler also checks the subset types, which LLVM's do not tell apart;
  - effects: R if it may raise in the runtime the driver builds (runtime.py linked with runtime.c
    and optimized with opt -O2): a raise statement, or a raise it reaches there that opt could not
    remove, but those of the subset's index, divisor, shift and conversion checks (BUG_ONLY), which fire only on a bug
    of runtime.py, as runtime.c's unchecked indexing would misbehave; an overflow check counts,
    as CPython raises OverflowError for a result too long too (replace, join), and a MemoryError
    is A. A if it allocates, U if it runs user code, I if it does I/O: through the runtime
    functions it calls (their entries, or runtime.c's call graph for a function runtime.py
    declares). runtime.c's functions that call runtime.py's (hsh calls pys_hash_str) get those
    letters too;
  - recursion: no function of runtime.py reaches itself through an operation's lowering (an rt op)
    or through runtime.c. The compiler rejects an operation that lowers to the function it is in;
    a cycle through a helper (helper -> math.gcd -> pys_m_gcd -> helper) or through runtime.c
    (pys_format_str formatting with a nested spec, which calls runtime.c's pys_format, which calls
    pys_format_str) would recurse without end where nothing in the source shows a call. Recursion
    by name stays allowed; the check is conservative, as it does not follow descriptors (a str ==
    in pys_hash_str would be reported, through pys_eq's dict case).
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
# functions whose call graph reaches user code only through comparing a key (eqv) or a KeyError's
# repr of the key: dict keys are ints, strs, or tuples of int, bool, str, None and such tuples,
# which compare and print without user code
NO_USER = {"dict.has", "dict.find", "dict.getitem", "dict.entry", "dict.get", "dict.set", "dict.pop", "dict.pop_default",
           "dict.setdefault", "dict.getbox", "dict.popbox"}
RAISES = {"pys_fail", "pys_raise", "oserr", "kbint_exit"}
USER = {"pys_obj_eq", "pys_obj_cmp", "pys_obj_repr"}
# the functions that walk a value by its descriptor (its static type), reading the lists and dicts in it
BY_DESC = {"eqv", "opv", "repr"}
# the messages of the subset's implicit checks that fire only on a bug of runtime.py: an index out
# of range (its primitives' and s[i]'s), a zero divisor, a negative shift count, a float that does
# not fit an int, a square root's domain (runtime.py raises what a caller may cause with raise)
BUG_ONLY = ("IndexError: string index out of range", "IndexError: compare out of range", "IndexError: search out of range",
            "IndexError: copy out of range", "IndexError: list index out of range", "IndexError: list assignment index out of range",
            "ValueError: byte must be in range(0, 256)", "ZeroDivisionError: integer division or modulo by zero",
            "ValueError: negative shift count", "OverflowError: cannot convert float infinity to integer",
            "ValueError: cannot convert float NaN to integer", "ValueError: math domain error")
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


def runtime_py(pys):
    # the IR the compiler builds for runtime.py: (its LLVM text, symbol -> the ops of each function
    # it compiles, as (op, text immediate, descriptor) triples, captured before they are lowered).
    # The ops of its cold blocks, which raise what its implicit checks find, are left out
    path = os.path.join(ROOT, "runtime.py")
    ops = {}

    class Capture(pys.Gen):
        def lower(self, fn):
            cold = set(fn.cold.values())
            ops[fn.f.ll[1:]] = [(i.op, i.s, i.x) for b in fn.blocks if b.label not in cold for i in b.code]
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


def linked(rpy_ir, tmp):
    # runtime.py's IR linked with runtime.c's and optimized, as the driver builds the cached
    # runtime: (name -> its function (as functions gives it), name -> the messages of the raises in
    # its body: "Kind: text" of a pys_raise or the format of a pys_fail, "?" if not a constant)
    rpy = os.path.join(tmp, "rtpy.ll")
    with open(rpy, "w", encoding="latin-1") as f:
        f.write(rpy_ir)
    rc = os.path.join(tmp, "runtime-c.ll")
    out = subprocess.run([TOOL + "clang", "-O2", "-S", "-emit-llvm", os.path.join(ROOT, "runtime.c"), "-o", rc], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"check_runtime: clang cannot compile runtime.c:\n{out.stderr}")
    with open(rc, encoding="latin-1") as f:
        c = re.sub(r' "(target-cpu|target-features|tune-cpu)"="[^"]*"', "", f.read())  # (as the driver strips them)
    with open(rc, "w", encoding="latin-1") as f:
        f.write(c)
    lk = os.path.join(tmp, "linked.bc")
    opt = os.path.join(tmp, "opt.ll")
    for cmd in ([TOOL + "llvm-link", rpy, rc, "-o", lk], [TOOL + "opt", "-O2", "-S", lk, "-o", opt]):
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit(f"check_runtime: {' '.join(cmd)}:\n{out.stderr}")
    with open(opt, encoding="latin-1") as f:
        ll = f.read()
    text = {}
    for m in re.finditer(r'^(@[\w.]+) = .*?c"((?:[^"\\]|\\[0-9A-Fa-f]{2})*)\\00"', ll, re.M):
        text[m.group(1)] = re.sub(r"\\([0-9A-Fa-f]{2})", lambda h: chr(int(h.group(1), 16)), m.group(2))
    msgs = {}
    cur = None
    for line in ll.split("\n"):
        m = re.match(r"define .*?@([\w.]+)\(", line)
        if m:
            cur = m.group(1)
            msgs[cur] = set()
        elif line == "}":
            cur = None
        elif cur is not None:
            r = re.search(r"call void @pys_raise\(ptr (?:nonnull )?(@[\w.]+), ptr (?:nonnull )?(@[\w.]+)\)", line)
            if r:
                msgs[cur].add(f"{text.get(r.group(1), '?')}: {text.get(r.group(2), '?')}")
            elif re.search(r"@(pys_raise|pys_fail|failf|oserr|kbint_exit)\b", line) and " call " in f" {line} ":
                r = re.search(r"@(?:pys_fail|failf)\(ptr (?:noundef )?(?:nonnull )?(@[\w.]+)", line)
                msgs[cur].add(text.get(r.group(1), "?") if r else "?")
    return functions(ll), msgs


def raises(fns, msgs, f):
    # the messages of the raises f reaches in the linked runtime, the allocator's aside (gc_slow);
    # the raising functions' own bodies too, as their callers' messages say what they raise
    seen = set()
    todo = [f]
    out = set()
    while todo:
        g = todo.pop()
        if g in seen or g in ("gc_slow", "pys_fail", "failf", "pys_raise"):
            continue
        seen.add(g)
        out |= msgs.get(g, set())
        if g in fns:
            todo.extend(fns[g][3])
    return out


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
# an rt edge between runtime.py's functions goes through a node of its own ("rt:" + callee)
assert cycle({"h": {"rt:g"}, "rt:g": {"g"}, "g": {"h"}}, "g", {"rt:g"}) == ["g", "h", "rt:g", "g"]


def main():
    verbose = "-v" in sys.argv[1:]
    pys = load_compiler()
    rt = pys.RUNTIME
    bad = []
    note = []
    ll = llvm_ir(os.path.join(ROOT, "runtime.c"), "runtime.c")
    fns = functions(ll)
    rpy_ir, rpy_ops = runtime_py(pys)
    # effects of runtime.py's functions (see the docstring): R from the linked runtime; A, U and I
    # from the ops, through the functions they call, to a fixpoint
    with tempfile.TemporaryDirectory() as tmp:
        lfns, lmsgs = linked(rpy_ir, tmp)
    letters = {}  # runtime.py's function -> the effect letters derived (R A U I)
    writes = {}
    used = state(ll)
    pure = set(PURE_C)
    PURE_C.update(rpy_ops)  # (while runtime.py's own functions get their letters, below)
    via = {}  # a function of runtime.c that runtime.py declares -> runtime.py's functions it calls
    for f, ops in rpy_ops.items():
        m = set()
        if any(x != "?" and not x.startswith(BUG_ONLY) and not x.startswith("MemoryError") or x == "?" for x in raises(lfns, lmsgs, f)):
            m.add("R")
        for op, x, d in ops:
            if op == "raise":
                m.add("R")  # (an explicit raise statement, whatever its message)
            if op == "rt" and pys.rtsym(x) not in rpy_ops:
                e = rt[x]
                ls = e[e.find("|") + 1 : e.rfind("|")].split()
                m.update(y for y in ls if y in ("A", "U", "I"))
                if "U?" in ls and "O" in d:
                    m.add("U")  # (as Gen.opfx: when the descriptor holds a class)
            elif op == "call" and x[1:] not in rpy_ops:
                # one of runtime.c's functions, which runtime.py declares: its entry, if RUNTIME
                # names it, and what runtime.c's call graph shows
                if x[1:] in pys.RTSYM:
                    e = rt[pys.RTSYM[x[1:]]]
                    m.update(y for y in e[e.find("|") + 1 : e.rfind("|")].split() if y in ("A", "U", "I"))
                if reaches(fns, x[1:], {"gc_slow"}, set()):
                    m.add("A")
                if reaches(fns, x[1:], USER, set()):
                    m.add("U")
                if uses_state(fns, used, x[1:]):
                    m.add("I")
                via[x[1:]] = {g for g in rpy_ops if reaches(fns, x[1:], {g}, set())}
        letters[f] = m
        # (whether it may write memory it did not allocate: an rt op that writes lists, dicts,
        # objects, globals or files, or a function of runtime.c it declares)
        writes[f] = any(op == "call" and x[1:] not in rpy_ops or op == "rt" and pys.rtsym(x) not in rpy_ops and
                        any(w in rt[x][rt[x].find("|") + 1 : rt[x].rfind("|")].split() for w in ("wL", "wD", "wO", "wG", "wF")) for op, x, _ in ops)
    more = True
    while more:
        more = False
        for f, ops in rpy_ops.items():
            for op, x, _ in ops:
                g = pys.rtsym(x) if op == "rt" else x[1:] if op == "call" else ""
                for h in via.get(g, set()) | {g}:
                    if h in letters and h != f and (not letters[h] <= letters[f] or writes[h] and not writes[f]):
                        letters[f] |= letters[h]
                        writes[f] = writes[f] or writes[h]
                        more = True
    # runtime.c calls some of them (hsh calls pys_hash_str): to the analysis of runtime.c below,
    # one that uses no state is as a pure C library function, and one that writes nothing it was
    # given only reads its arguments (runtime mode has no globals)
    PURE_C.clear()
    PURE_C.update(pure)
    for f in rpy_ops:
        if "I" not in letters[f]:
            PURE_C.add(f)
        if not writes[f]:
            READS_ONLY.add(f)
    eff = params(llvm_ir(os.path.join(ROOT, "runtime.c"), "runtime.c", "-O1"))
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
        have = fns.get(sym) if sym in fns and fns[sym][4] == "define" else cfns.get(sym)
        if have is None:
            bad.append(f"{k}: neither runtime.c nor runtime.py defines {sym}" + (" (runtime.c only declares it)" if sym in fns else ""))
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
    # effects of runtime.c's functions: what their call graph shows, runtime.py's functions they
    # call included (with the letters derived above)
    pyr = {f for f in letters if "R" in letters[f]}
    pya = {f for f in letters if "A" in letters[f]}
    pyu = {f for f in letters if "U" in letters[f]}
    for k in rt:
        sym = pys.rtsym(k)
        if sym not in fns or sym in rpy_ops:
            continue
        e = rt[k]
        have = e[e.find("|") + 1 : e.rfind("|")].split()
        for x in have:
            if x not in pys.FX and x != "U?":
                bad.append(f"{k}: {x} is no effect letter (FX)")
        derived = []
        if reaches(fns, sym, RAISES | pyr, {"gc_slow"}):
            derived.append("R")
        if fns[sym][2]:
            derived.append("N")
        if reaches(fns, sym, {"gc_slow"} | pya, set()):
            derived.append("A")
        if reaches(fns, sym, USER | pyu, set()) and k not in NO_USER:
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
            if x not in have and "U" not in have and not (x == "U" and "U?" in have):
                bad.append(f"{k}: {sym} has effect {x} in runtime.c, which RUNTIME leaves out")
        for x in ("R", "N", "A", "I", "rL", "wL", "rD", "wD", "rF", "wF"):
            if x in have and x not in derived:
                note.append(f"{k}: {x}, which runtime.c does not show")
    # recursion: an rt op that calls a function of runtime.py goes through a node of its own, so
    # that a cycle through it, or through runtime.c, is found
    graph = {n: v[3] for n, v in fns.items() if v[4] == "define"}
    for f, ops in rpy_ops.items():
        graph[f] = set()
        for op, x, _ in ops:
            g = pys.rtsym(x) if op == "rt" else x[1:] if op == "call" else ""
            if op == "rt" and g in rpy_ops:
                graph[f].add("rt:" + g)
                graph["rt:" + g] = {g}
            elif g != "":
                graph[f].add(g)
    inner = {n for n in graph if n not in rpy_ops}
    for f in sorted(rpy_ops):
        c = cycle(graph, f, inner)
        if c:
            bad.append(f"runtime.py's {f} reaches itself through an operation's lowering or runtime.c ({' -> '.join(c)}): it would recurse without end")
    for b in bad:
        print(b)
    if verbose:
        for n in note:
            print("note:", n)
    print(f"{len(rt)} RUNTIME entries: " + (f"{len(bad)} problems" if bad else f"signatures, coverage and effects agree with runtime.c and runtime.py ({len(rpy_ops)} functions, none of which reaches itself through a lowering or runtime.c)"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
