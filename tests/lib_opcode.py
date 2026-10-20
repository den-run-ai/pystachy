# opcode, CPython's own module, on lib's _opcode stand-in: its tables, its lists of opcodes, and
# stack_effect() of every opcode at the edges of the C int that CPython reads an oparg as
import opcode
import _opcode
from _opcode import stack_effect
from typing import Callable

print(len(opcode.opname), opcode.opname[:6], opcode.opname[-3:])
print(opcode.opmap["LOAD_CONST"], opcode.opmap["CALL"], opcode.opmap["JUMP"], opcode.opmap["SETUP_WITH"])
print(opcode.HAVE_ARGUMENT, opcode.EXTENDED_ARG, opcode.MIN_INSTRUMENTED_OPCODE, opcode.cmp_op, opcode.hascompare)
print("hasarg", len(opcode.hasarg), opcode.hasarg[:12])
print("hasconst", opcode.hasconst, "hasname", opcode.hasname)
print("hasjump", opcode.hasjump, opcode.hasjrel is opcode.hasjump, opcode.hasjabs)
print("hasfree", opcode.hasfree, "haslocal", opcode.haslocal, "hasexc", opcode.hasexc)
print(opcode._nb_ops[0], opcode._nb_ops[13], len(opcode._nb_ops))
print(opcode._intrinsic_1_descs)
print(opcode._intrinsic_2_descs)
print(opcode._inline_cache_entries)
print(sorted(opcode._specializations["LOAD_ATTR"]), opcode._specialized_opmap["LOAD_ATTR_SLOT"])



# the predicates of every opcode, and of numbers no opcode has
def show(name: str, f: Callable[[int], bool]) -> None:
    ops = [op for op in range(-3, 300) if f(op)]
    print(name, len(ops), ops[:4], ops[-4:], f(-2147483648), f(2147483647))


show("is_valid", _opcode.is_valid)
show("has_arg", _opcode.has_arg)
show("has_const", _opcode.has_const)
show("has_name", _opcode.has_name)
show("has_jump", _opcode.has_jump)
show("has_free", _opcode.has_free)
show("has_local", _opcode.has_local)
show("has_exc", _opcode.has_exc)

# stack_effect(): each opcode's effect, its effect when jumping and not, for opargs at the edges of
# a C int and around them (CPython keeps an oparg's low 32 bits, and its int arithmetic wraps)
opargs = [0, 1, 2, 3, 4, 255, 256, 257, 65535, 65536, 2147483645, 2147483646, 2147483647, 2147483648,
          4294967295, 4294967296, 4294967301, -1, -2, -256, -2147483647, -2147483648, -2147483649,
          9223372036854775807, -9223372036854775808]
valid = 0
invalid = 0
digest = 0
for op in range(-2, 270):
    for oparg in opargs:
        for jump in (0, 1, 2):
            try:
                if jump == 0:
                    e = stack_effect(op, oparg)
                else:
                    e = stack_effect(op, oparg, jump=jump == 1)
                valid += 1
                digest = (digest * 1000003 + e + op) % 1000000007
            except ValueError:
                invalid += 1
print("stack_effect:", valid, "valid,", invalid, "invalid, digest", digest)
for name in ("POP_TOP", "BUILD_LIST", "CALL", "UNPACK_EX", "BUILD_MAP", "FORMAT_WITH_SPEC", "SETUP_FINALLY",
             "SETUP_CLEANUP", "LOAD_CLOSURE", "STORE_FAST_MAYBE_NULL", "JUMP_NO_INTERRUPT"):
    op = opcode.opmap[name]
    out: list[str] = []
    for oparg in (0, 3, -1, 2147483645, 2147483646, -2147483649, 4294967301):
        try:
            out.append(str(stack_effect(op, oparg)))
        except ValueError:
            out.append("-")
    print(name, " ".join(out), stack_effect(op, 1, jump=True), stack_effect(op, 1, jump=False))
print(stack_effect(opcode.opmap["POP_TOP"]), stack_effect(opcode.opmap["SETUP_WITH"]), stack_effect(opcode.opmap["SETUP_WITH"], None, jump=False))
print(stack_effect(opcode.opmap["BUILD_LIST"], 1), _opcode.is_valid(opcode=1))

for op in (2147483648, -2147483649, 9223372036854775807):
    try:
        stack_effect(op)
    except OverflowError as e:
        print("OverflowError:", e)
    try:
        _opcode.has_jump(op)
    except OverflowError as e:
        print("OverflowError:", e)
for op in (30000, -1, opcode._specialized_opmap["LOAD_ATTR_SLOT"], 236):
    try:
        print(stack_effect(op, 1))
    except ValueError as e:
        print("ValueError:", e, op)

# the other functions
nb = _opcode.get_nb_ops()
nb.append(("X", "x"))
print(len(_opcode.get_nb_ops()), _opcode.get_intrinsic1_descs()[1], _opcode.get_intrinsic2_descs()[1])
print(_opcode.get_specialization_stats())


class Code:
    pass


for offset in (0, 2147483648):
    try:
        _opcode.get_executor(Code(), offset)
    except TypeError as e:
        print("TypeError:", e)
    except OverflowError as e:
        print("OverflowError:", e)
try:
    _opcode.get_executor([1], 1)
except TypeError as e:
    print("TypeError:", e)
print(opcode.stack_effect is stack_effect, _opcode.__doc__)
