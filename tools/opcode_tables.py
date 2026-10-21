"""Write lib/_pystachy_opcode_db.py: the tables of the _opcode stand-in (lib/_pystachy_opcode.py),
from CPython's own sources and module.

usage: python3 -I tools/opcode_tables.py INCLUDE_DIR [LIBDIR]
       (with the CPython whose _opcode lib/ ports; INCLUDE_DIR is that version's Include/, which holds
       opcode_ids.h and internal/pycore_opcode_metadata.h; LIBDIR is lib/)
Tools/cases_generator makes both headers from Python/bytecodes.c, as it makes Lib/_opcode_metadata.py:
- each opcode's number (opcode_ids.h), and HAVE_ARGUMENT and MIN_INSTRUMENTED_OPCODE;
- its flags (_PyOpcode_opcode_metadata), which has_arg() and the other predicates test;
- the opcode each specialized one stands for (_PyOpcode_Deopt), as stack_effect() needs;
- how many items each one pops and pushes (_PyOpcode_num_popped() and _num_pushed()), whose
  difference stack_effect() gives: a C expression of the oparg, from a small set this parses.
The names of the binary operators and the intrinsics are what CPython's _opcode gives. Every table
is then checked against that module, every predicate of every opcode and stack_effect() of every
real opcode, for each jump, over 4,000 opargs at the edges of a C int and between them, before
anything is written.
"""
import os
import re
import sys

sys.dont_write_bytecode = True  # (no __pycache__ in lib/)

# the C expressions of _PyOpcode_num_popped() and _num_pushed(), as KIND, C: _pystachy_opcode._count()
# computes each one in C int arithmetic
EXPRS = [
    (re.compile(r"(\d+)"), 0, lambda m: int(m.group(1))),  # C
    (re.compile(r"oparg"), 1, lambda m: 0),  # C + oparg
    (re.compile(r"(\d+) \+ oparg"), 1, lambda m: int(m.group(1))),
    (re.compile(r"(\d+) \+ \(oparg ?- ?(\d+)\)"), 1, lambda m: int(m.group(1)) - int(m.group(2))),
    (re.compile(r"(\d+) \+ \(oparg & 1\)"), 2, lambda m: int(m.group(1))),  # C + (oparg & 1)
    (re.compile(r"oparg\*2"), 3, lambda m: 0),  # C + 2 * oparg
    (re.compile(r"(\d+) \+ \(oparg >> 8\) \+ \(oparg & 0xFF\)"), 4, lambda m: int(m.group(1))),  # C + (oparg >> 8) + (oparg & 0xFF)
    (re.compile(r"(\d+) \+ \(\(oparg == 3\) \? 1 : 0\)"), 5, lambda m: int(m.group(1))),  # C + (1 if oparg == 3 else 0)
]
NOCASE = -1  # an opcode the switch has no case for: its default returns -1
FLAGNAMES = ["HAS_ARG_FLAG", "HAS_CONST_FLAG", "HAS_NAME_FLAG", "HAS_JUMP_FLAG", "HAS_FREE_FLAG", "HAS_LOCAL_FLAG"]


def body(text, start, end):
    i = text.index(start)
    return text[i : text.index(end, i)]


def opcodes(ids):
    # the opcodes' numbers, in opcode_ids.h's order
    out = {}
    for name, n in re.findall(r"^#define (\w+) +(\d+)$", ids, re.M):
        out[name] = int(n)
    return out


def switch(text, fn, num):
    # fn's switch, from each opcode's number to its expression's KIND, C
    src = body(text, f"int {fn}(int opcode, int oparg)  {{", "\n}\n")
    out = {}
    cases = []
    for line in src.splitlines():
        line = line.strip()
        m = re.fullmatch(r"case (\w+):", line)
        if m:
            cases.append(num[m.group(1)])
            continue
        m = re.fullmatch(r"return (.*);", line)
        if m is None:
            continue
        if not cases:
            if m.group(1) != "-1":
                sys.exit(f"{fn}: the default returns {m.group(1)}, not -1")
            continue
        for rx, kind, c in EXPRS:
            e = rx.fullmatch(m.group(1))
            if e:
                for op in cases:
                    out[op] = (kind, c(e))
                break
        else:
            sys.exit(f"{fn}: unknown expression {m.group(1)!r}")
        cases = []
    return out


def metadata(text, num, flagval):
    # each opcode's flags, from its _PyOpcode_opcode_metadata entry
    src = body(text, "const struct opcode_metadata _PyOpcode_opcode_metadata[268] = {", "};")
    out = {}
    for name, valid, flags in re.findall(r"\[(\w+)\] = \{ (true|false), [^,]+, ([^}]*?) \}", src):
        if valid != "true":
            continue
        f = 0
        for x in flags.split("|"):
            x = x.strip()
            f |= int(x) if x.isdigit() else flagval[x]
        out[num[name]] = f
    return out


def deopt(text, num):
    src = body(text, "const uint8_t _PyOpcode_Deopt[256] = {", "};")
    return {num[a]: num[b] for a, b in re.findall(r"\[(\w+)\] = (\w+),", src)}


def tuples(name, items, per=16):
    rows = [", ".join(str(x) for x in items[i : i + per]) for i in range(0, len(items), per)]
    return f"{name} = (\n" + "".join(f"    {r},\n" for r in rows) + ")\n"


def check(db, lib):
    # every table against CPython's own module: lib's stand-in, on these tables, against _opcode
    import _opcode
    import importlib.util
    import types

    tables = types.ModuleType("_pystachy_opcode_db")
    for name, value in db.items():
        setattr(tables, name, value)
    sys.modules["_pystachy_opcode_db"] = tables
    spec = importlib.util.spec_from_file_location("_pystachy_opcode", os.path.join(lib, "_pystachy_opcode.py"))
    port = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(port)
    n = 0
    for op in range(-300, 600):
        for f in ["is_valid", "has_arg", "has_const", "has_name", "has_jump", "has_free", "has_local", "has_exc"]:
            if getattr(port, f)(op) != getattr(_opcode, f)(op):
                sys.exit(f"{f}({op}): {getattr(port, f)(op)}, CPython's {getattr(_opcode, f)(op)}")
            n += 1
    edges = list(range(-1000, 1000)) + [2**31 - 1 - k for k in range(500)] + [-(2**31) + k for k in range(500)]
    for op in range(0, 300):
        for oparg in [None] + edges:
            for jump in [None, True, False]:
                a, b = outcome(port.stack_effect, op, oparg, jump), outcome(_opcode.stack_effect, op, oparg, jump)
                if a != b:
                    sys.exit(f"stack_effect({op}, {oparg}, jump={jump}): {a}, CPython's {b}")
                n += 1
    for f in ["get_nb_ops", "get_intrinsic1_descs", "get_intrinsic2_descs"]:
        if getattr(port, f)() != getattr(_opcode, f)():
            sys.exit(f"{f}(): {getattr(port, f)()}, CPython's {getattr(_opcode, f)()}")
    return n


def outcome(f, op, oparg, jump):
    try:
        return f(op, oparg, jump=jump)
    except ValueError as e:
        return f"ValueError: {e}"


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python3 -I tools/opcode_tables.py INCLUDE_DIR [LIBDIR]")
    inc = sys.argv[1]
    lib = sys.argv[2] if len(sys.argv) == 3 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
    ids = open(os.path.join(inc, "opcode_ids.h")).read()
    meta = open(os.path.join(inc, "internal", "pycore_opcode_metadata.h")).read()
    num = opcodes(ids)
    flagval = {k: int(v) for k, v in re.findall(r"^#define (HAS_\w+_FLAG) \((\d+)\)$", meta, re.M)}
    flags = metadata(meta, num, flagval)
    de = deopt(meta, num)
    popped = switch(meta, "_PyOpcode_num_popped", num)
    pushed = switch(meta, "_PyOpcode_num_pushed", num)
    real = 255  # MAX_REAL_OPCODE + 1 (pycore_opcode_utils.h)
    db = {
        "HAVE_ARGUMENT": num["HAVE_ARGUMENT"],
        "MIN_INSTRUMENTED_OPCODE": num["MIN_INSTRUMENTED_OPCODE"],
        "FLAGS": tuple(flags.get(op, -1) for op in range(268)),
        "DEOPT": tuple(de.get(op, 0) for op in range(real)),
        "POP_KIND": tuple(popped.get(op, (NOCASE, 0))[0] for op in range(real)),
        "POP_C": tuple(popped.get(op, (NOCASE, 0))[1] for op in range(real)),
        "PUSH_KIND": tuple(pushed.get(op, (NOCASE, 0))[0] for op in range(real)),
        "PUSH_C": tuple(pushed.get(op, (NOCASE, 0))[1] for op in range(real)),
    }
    for name in ["JUMP", "JUMP_NO_INTERRUPT", "LOAD_CLOSURE", "LOAD_METHOD", "LOAD_SUPER_METHOD", "LOAD_ZERO_SUPER_ATTR",
                 "LOAD_ZERO_SUPER_METHOD", "POP_BLOCK", "SETUP_CLEANUP", "SETUP_FINALLY", "SETUP_WITH", "STORE_FAST_MAYBE_NULL"]:
        db[name] = num[name]  # the pseudo-instructions, which compile.c's stack_effect() decides itself
    import _opcode

    db["NB_OPS"] = tuple(_opcode.get_nb_ops())
    db["INTRINSIC1"] = tuple(_opcode.get_intrinsic1_descs())
    db["INTRINSIC2"] = tuple(_opcode.get_intrinsic2_descs())
    n = check(db, lib)
    bits = ", ".join(f"{x} {flagval[x]}" for x in FLAGNAMES)
    out = [
        f"# Generated by tools/opcode_tables.py from CPython {sys.version.split()[0]}: do not edit. The tables of the\n"
        "# _opcode stand-in (_pystachy_opcode.py), from Include/opcode_ids.h and\n"
        "# Include/internal/pycore_opcode_metadata.h, which CPython's Tools/cases_generator makes from\n"
        "# Python/bytecodes.c. FLAGS[op], for op below 268, is _PyOpcode_opcode_metadata[op].flags, or -1 where\n"
        "# that table has no entry for op; the predicates test the flags\n"
        f"# {bits}.\n"
        "# DEOPT[op], for op below 255, is _PyOpcode_Deopt[op], the opcode that a specialized op stands for (0\n"
        "# where it has no entry).\n"
        "# POP_KIND[op], POP_C[op] and PUSH_KIND[op], PUSH_C[op] are _PyOpcode_num_popped(op, oparg) and\n"
        "# _num_pushed(): the KIND of C expression of the oparg that op's case returns, or -1 for an op the switch\n"
        "# has no case for, and the constant C in it (_pystachy_opcode._count()). NB_OPS, INTRINSIC1 and\n"
        "# INTRINSIC2 are what CPython's _opcode.get_nb_ops(), get_intrinsic1_descs() and get_intrinsic2_descs()\n"
        "# give.\n\n",
        f"HAVE_ARGUMENT = {db['HAVE_ARGUMENT']}\n",
        f"MIN_INSTRUMENTED_OPCODE = {db['MIN_INSTRUMENTED_OPCODE']}\n",
    ]
    for name in ["JUMP", "JUMP_NO_INTERRUPT", "LOAD_CLOSURE", "LOAD_METHOD", "LOAD_SUPER_METHOD", "LOAD_ZERO_SUPER_ATTR",
                 "LOAD_ZERO_SUPER_METHOD", "POP_BLOCK", "SETUP_CLEANUP", "SETUP_FINALLY", "SETUP_WITH", "STORE_FAST_MAYBE_NULL"]:
        out.append(f"{name} = {db[name]}\n")
    out.append("\n")
    for name in ["FLAGS", "DEOPT", "POP_KIND", "POP_C", "PUSH_KIND", "PUSH_C"]:
        out.append(tuples(name, db[name]))
    out.append("NB_OPS = (\n" + "".join(f"    {x!r},\n" for x in db["NB_OPS"]) + ")\n")
    for name in ["INTRINSIC1", "INTRINSIC2"]:
        out.append(f"{name} = (\n" + "".join(f"    {x!r},\n" for x in db[name]) + ")\n")
    with open(os.path.join(lib, "_pystachy_opcode_db.py"), "w") as f:
        f.write("".join(out))
    print(f"wrote {os.path.join(lib, '_pystachy_opcode_db.py')}: {n} checks against CPython's _opcode")


if __name__ == "__main__":
    main()
