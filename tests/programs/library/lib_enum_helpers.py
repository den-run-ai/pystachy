# enum's helpers and constants: FlagBoundary's and EnumCheck's members (STRICT, ..., UNIQUE, ...,
# StrEnum members of the module, as their classes are), show_flag_values() and _iter_bits_lsb()
# of ints and flags (whose ValueError for a negative number comes as iteration starts),
# _is_dunder(), _is_sunder(), _is_private() and _is_single_bit() of the names CPython's
# test_enum asks about, bin(), and global_enum_repr(), global_flag_repr() and global_str() of
# members.
import enum
from enum import (CONFORM, CONTINUOUS, EJECT, KEEP, NAMED_FLAGS, STRICT, UNIQUE, EnumCheck, Flag,
                  FlagBoundary, IntEnum, IntFlag, _iter_bits_lsb, show_flag_values)


class Perm(Flag):
    R = 4
    W = 2
    X = 1


class Mode(IntFlag, boundary=KEEP):
    A = 1
    B = 2


class Level(IntEnum):
    LOW = 1
    HIGH = 2


print(STRICT, repr(CONFORM), str(EJECT), KEEP.value, list(FlagBoundary), FlagBoundary("keep") is KEEP, len(FlagBoundary))
print(repr(UNIQUE), str(CONTINUOUS), NAMED_FLAGS.name, list(EnumCheck), EnumCheck.UNIQUE is UNIQUE, "keep" in FlagBoundary)
print(show_flag_values(13), show_flag_values(0), show_flag_values(Perm.R | Perm.X), enum.show_flag_values(Mode(9)))
print(list(_iter_bits_lsb(7)), list(_iter_bits_lsb(Level.HIGH)), list(_iter_bits_lsb(2 ** 62 + 1)))
bits = _iter_bits_lsb(-8)
print("made")
try:
    list(bits)
except ValueError as e:
    print("ValueError", e)
for name in ["_bad_", "__mal__", "_MyEnum__private", "_MyEnum__private_", "okay", "_semi_private", "_weird__", "_MyEnum__", "_", "__", "_a_", "__a__"]:
    print(name, enum._is_sunder(name), enum._is_dunder(name), enum._is_private("MyEnum", name))
print(enum._is_single_bit(8), enum._is_single_bit(6), enum._is_single_bit(0), enum.bin(10), enum.bin(~10), enum.bin(5, 8))
print(enum.global_enum_repr(Level.LOW), enum.global_flag_repr(Perm.R | Perm.W), enum.global_flag_repr(Perm(0)), enum.global_flag_repr(Mode(9)))
print(enum.global_str(Perm.R), enum.global_str(Perm(0)), enum.global_str(Level.HIGH), enum.pickle_by_global_name(Level.LOW, 2))
