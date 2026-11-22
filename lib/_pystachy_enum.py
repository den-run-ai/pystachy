# Pystachy's part of CPython 3.13.16's Lib/enum.py that a program reads only where it names it
# (lib/compatibility.md#enum): FlagBoundary and EnumCheck, CPython's StrEnum classes of enum, with
# their members as the module's constants (STRICT, ..., UNIQUE, ...), and verify, which reads
# them. A module's import of one of these names from enum, or its read of enum.NAME, is one of
# this module's (Loader's enum_elsewhere), where the module reads the name otherwise than as a
# flag class's boundary= or an enum class's @verify(...), which the compiler applies: an enum
# value of a program may hold a member of these classes only where the program names them, as
# the compiler sees each class of the program that derives from Enum.
from enum import StrEnum, _FlagType, _bits, _is_single_bit, _iter_bits_lsb, auto


class EnumCheck(StrEnum):
    """
    various conditions to check an enumeration for
    """
    # (CPython's @_simple_enum(StrEnum) class, of the same members; the compiler checks an enum
    # class that @verify(...) decorates)
    CONTINUOUS = "no skipped integer values"
    NAMED_FLAGS = "multi-flag aliases may not contain unnamed flags"
    UNIQUE = "one name per value"


CONTINUOUS = EnumCheck.CONTINUOUS
NAMED_FLAGS = EnumCheck.NAMED_FLAGS
UNIQUE = EnumCheck.UNIQUE


class FlagBoundary(StrEnum):
    """
    control how out of range values are handled
    "strict" -> error is raised             [default for Flag]
    "conform" -> extra bits are discarded
    "eject" -> lose flag status
    "keep" -> keep flag status and all bits [default for IntFlag]
    """
    # (a flag class's boundary=, which the compiler applies: its _FlagType object keeps the
    # boundary's value)
    STRICT = auto()
    CONFORM = auto()
    EJECT = auto()
    KEEP = auto()


STRICT = FlagBoundary.STRICT
CONFORM = FlagBoundary.CONFORM
EJECT = FlagBoundary.EJECT
KEEP = FlagBoundary.KEEP


class verify:
    """
    Check an enumeration for various constraints. (see EnumCheck)
    """
    # (the compiler applies @verify(...) to the enum class statement it decorates and reports a
    # failed check as an error: CPython's ValueError where the class statement runs. A direct
    # call takes the class as a value, its EnumType or _FlagType object, and checks it here)
    def __init__(self, *checks):
        self.checks = checks

    def __call__(self, enumeration):
        # (CPython's checks, each a function here, which names its own variables' types)
        for check in self.checks:
            if check is UNIQUE:
                _verify_unique(enumeration)
            elif check is CONTINUOUS:
                _verify_continuous(enumeration)
            elif check is NAMED_FLAGS:
                _verify_named_flags(enumeration)
        return enumeration


def _verify_unique(enumeration) -> None:
    # check for duplicate names
    duplicates = []
    for name, member in enumeration._member_map_.items():
        if name != member._name_:
            duplicates.append((name, member._name_))
    if duplicates:
        alias_details = ', '.join(
                ["%s -> %s" % (alias, name) for (alias, name) in duplicates])
        raise ValueError('aliases found in %r: %s' %
                (enumeration, alias_details))


def _verify_continuous(enumeration) -> None:
    enum_type = 'flag' if isinstance(enumeration, _FlagType) else 'enum'
    values = set([e._value_ for e in enumeration._member_list_])
    if len(values) < 2:
        return
    missing = _missing_values(values, enum_type == 'flag')
    if missing:
        raise ValueError(('invalid %s %r: missing values %s' % (
                enum_type, enumeration._cls_name_, ', '.join([str(m) for m in missing]))
                )[:256])
                # limit max length to protect against DOS attacks


def _verify_named_flags(enumeration) -> None:
    # examine each alias and check for unnamed flags
    member_names = [m._name_ for m in enumeration._member_list_]
    member_values = [m._value_ for m in enumeration._member_list_]
    missing_names = []
    missing_value = 0
    for name, member in enumeration._member_map_.items():
        if name in member_names:
            # not an alias
            continue
        missed = _unnamed_bits(member._value_, member_values)
        if missed:
            missing_names.append(name)
            for val in missed:
                missing_value |= val
    if missing_names:
        if len(missing_names) == 1:
            alias = 'alias %s is missing' % missing_names[0]
        else:
            alias = 'aliases %s and %s are missing' % (
                    ', '.join(missing_names[:-1]), missing_names[-1]
                    )
        if _is_single_bit(missing_value):
            value = 'value 0x%x' % missing_value
        else:
            value = 'combined values of 0x%x' % missing_value
        raise ValueError(
                'invalid Flag %r: %s %s [use enum.show_flag_values(value) for details]'
                % (enumeration._cls_name_, alias, value)
                )


def _high_bit(value: int) -> int:
    """
    returns index of highest bit, or -1 if value is zero or negative
    """
    return _bits(value) - 1


def _missing_values(values, flag: bool) -> list[int]:
    # verify(CONTINUOUS)'s missing values among the members' values, a set of two or more: the
    # powers of two between a flag's least and greatest, else the ints between them; CPython's
    # TypeError for values of another type, which have no ints between them. (A list of
    # missing values longer than the error message shows stops early)
    low, high = min(values), max(values)
    if isinstance(low, float):
        raise TypeError("'float' object cannot be interpreted as an integer")
    if not isinstance(low, int):
        raise TypeError(_concat_error(low))
    missing = []
    if flag:
        for i in range(_high_bit(low)+1, _high_bit(high)):
            if 2**i not in values:
                missing.append(2**i)
    else:
        shown = 0
        i = low + 1
        while i < high and shown <= 256:
            if i not in values:
                missing.append(i)
                shown += len(str(i)) + 2
            i += 1
    return missing


def _concat_error(low) -> str:
    # CPython's TypeError for low + 1, where low is a str, bytes or tuple
    if isinstance(low, bytes):
        return "can't concat int to bytes"
    return 'can only concatenate %s (not "int") to %s' % (type(low).__name__, type(low).__name__)


def _unnamed_bits(value, member_values) -> list[int]:
    # verify(NAMED_FLAGS)'s bits of an alias's value that no member has; none of a negative
    # value; CPython's TypeError for a value that is no int
    if isinstance(value, float):
        if value < 0 or not value:
            return []
        raise TypeError("bad operand type for unary ~: 'float'")
    if not isinstance(value, int):
        raise TypeError("'<' not supported between instances of '%s' and 'int'" % type(value).__name__)
    if value < 0:
        # negative numbers are not checked
        return []
    return [v for v in _iter_bits_lsb(value) if v not in member_values]
