"""Check lib/_pystachy_opcode.py on CPython against CPython's C module _opcode.

The port answers from the tables that tools/opcode_tables.py generates; this compares its answers
with the C module's: the predicates (is_valid(), has_arg() and the others) of every opcode up to 1100
from 0, either way, and at the edges of a C int; stack_effect() of every opcode up to 600, for each
jump argument, over the opargs at the edges of a C int and of a C long and between them, and of
random opcodes, opargs and jumps; the lists of the binary operators and intrinsics, fresh at each
call; get_specialization_stats(); get_executor() of objects that are not code objects (Pystachy has
none) and of offsets out of a C int's range. ENABLE_SPECIALIZATION must be 0, as Pystachy has no
specializing interpreter. The port's functions must have the C module's signatures, docstrings and
names, and the tables lib/_opcode_metadata.py's HAVE_ARGUMENT and MIN_INSTRUMENTED_OPCODE.
Usage: python3 -I tools/opcode_check.py [--rounds N]
"""
import _opcode
import argparse
import importlib.util
import inspect
from pathlib import Path
import random
import sys

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
PREDICATES = ["is_valid", "has_arg", "has_const", "has_name", "has_jump", "has_free", "has_local", "has_exc"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def outcome(f, *args, **kwargs):
    try:
        r = f(*args, **kwargs)
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return f"{type(r).__name__} {r!r}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=200000)
    options = parser.parse_args()
    load("_pystachy_opcode_db", LIB / "_pystachy_opcode_db.py")
    port = load("_opcode_port", LIB / "_pystachy_opcode.py")
    meta = load("_opcode_metadata_lib", LIB / "_opcode_metadata.py")
    gen = random.Random(20261019)
    count = failures = 0

    def report(what, got, want):
        nonlocal failures
        failures += 1
        if failures <= 20:
            print(f"{what}: {got}, where CPython's is {want}")

    def same(what, got, want):
        nonlocal count
        count += 1
        if got != want:
            report(what, got, want)

    edges = [2**31 - 1, 2**31, 2**31 + 1, -(2**31), -(2**31) - 1, 2**32 - 1, 2**32, 2**32 + 3, 2**63 - 1, -(2**63)]
    # the predicates, also of True and False (ints, as for CPython)
    for op in list(range(-1100, 1100)) + edges + [True, False]:
        for f in PREDICATES:
            same(f"{f}({op})", outcome(getattr(port, f), op), outcome(getattr(_opcode, f), op))
    same("is_valid(opcode=1)", outcome(port.is_valid, opcode=1), outcome(_opcode.is_valid, opcode=1))
    # stack_effect() at the edges of the oparg's C int (and the C long that CPython reads it as)
    opargs = [None, True, False] + list(range(-300, 300))
    for e in [2**31, 2**32, 2**63]:
        opargs += [e + k for k in range(-4, 4) if -(2**63) <= e + k < 2**63] + [-e + k for k in range(-4, 4) if -(2**63) <= -e + k]
    opargs += [256 * k + r for k in (1, 255, 256, 2**15, 2**23 - 1) for r in (0, 1, 255)]  # (UNPACK_EX's oparg >> 8 and & 0xFF)
    for op in list(range(-5, 600)) + edges:
        for oparg in opargs:
            for jump in [None, True, False]:
                same(f"stack_effect({op}, {oparg}, jump={jump})", outcome(port.stack_effect, op, oparg, jump=jump),
                     outcome(_opcode.stack_effect, op, oparg, jump=jump))
    same("stack_effect(1)", outcome(port.stack_effect, 1), outcome(_opcode.stack_effect, 1))
    # random opcodes, opargs and jumps
    for r in range(options.rounds):
        op = gen.choice([gen.randrange(-10, 280), gen.randrange(-(2**33), 2**33)])
        oparg = gen.choice([None, gen.randrange(-1000, 1000), gen.randrange(-(2**40), 2**40), gen.randrange(-(2**63), 2**63)])
        jump = gen.choice([None, True, False])
        same(f"stack_effect({op}, {oparg}, jump={jump})", outcome(port.stack_effect, op, oparg, jump=jump),
             outcome(_opcode.stack_effect, op, oparg, jump=jump))
    # the lists, which each call makes anew
    for f in ["get_nb_ops", "get_intrinsic1_descs", "get_intrinsic2_descs"]:
        a = getattr(port, f)()
        same(f"{f}()", a, getattr(_opcode, f)())
        a.append(a[0])
        same(f"{f}() after a change to the one before", getattr(port, f)(), getattr(_opcode, f)())
    same("get_specialization_stats()", outcome(port.get_specialization_stats), outcome(_opcode.get_specialization_stats))
    # get_executor() of what is not a code object: Pystachy has none

    class Item:
        pass

    for code in [0, "s", [1], None, 2.5, Item(), port.is_valid, range(3), b"x", (1,), {}, True]:
        for offset in [0, -1, 2**31 - 1, 2**31, -(2**31) - 1]:
            same(f"get_executor({code!r}, {offset})", outcome(port.get_executor, code, offset), outcome(_opcode.get_executor, code, offset))
    same("ENABLE_SPECIALIZATION", port.ENABLE_SPECIALIZATION, 0)
    same("HAVE_ARGUMENT", port._db.HAVE_ARGUMENT, meta.HAVE_ARGUMENT)
    same("MIN_INSTRUMENTED_OPCODE", port._db.MIN_INSTRUMENTED_OPCODE, meta.MIN_INSTRUMENTED_OPCODE)
    for name, op in meta.opmap.items():
        same(f"is_valid({name})", outcome(port.is_valid, op), outcome(_opcode.is_valid, op))
    # the C module's public names, signatures and docstrings
    for n in sorted(x for x in dir(_opcode) if not x.startswith("__")):
        a = getattr(_opcode, n)
        b = getattr(port, n, None)
        count += 1
        if b is None:
            report(n, "missing", "defined")
            continue
        if callable(a):
            same(f"{n}.__doc__", (b.__doc__ or "").rstrip(), (a.__doc__ or "").rstrip())
            mine = str(inspect.signature(b)).split(" -> ")[0]
            for ann in (": int | None", ": bool | None", ": int"):
                mine = mine.replace(ann, "")
            same(f"{n} signature", mine.replace(" = ", "="), str(inspect.signature(a)))
    same("names", sorted(x for x in dir(port) if not x.startswith("_")), sorted(x for x in dir(_opcode) if not x.startswith("_")))
    same("__doc__", port.__doc__, _opcode.__doc__)
    print(f"{count} checks, {failures} differ")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
