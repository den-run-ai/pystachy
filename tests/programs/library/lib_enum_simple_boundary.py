# CPython's re declares its flags so: @global_enum of an IntFlag class that @_simple_enum makes,
# with boundary=KEEP, whose body names each flag twice (ASCII = A = 256: A is ASCII's alias).
# Lookups and | keep bits no member has, repr() names the module's flags, and the module binds
# each name, aliases too.
import enum


@enum.global_enum
@enum._simple_enum(enum.IntFlag, boundary=enum.KEEP)
class RegexFlag:
    NOFLAG = 0
    ASCII = A = 256
    IGNORECASE = I = 2
    LOCALE = L = 4
    UNICODE = U = 32
    MULTILINE = M = 8
    DEBUG = 128


print(RegexFlag.A, repr(A), repr(I | M), repr(RegexFlag.I | 1), repr(RegexFlag(258)), repr(RegexFlag(0)))
print(str(ASCII), f"{I | M}", I is IGNORECASE, list(RegexFlag), len(RegexFlag), list(RegexFlag.__members__))
print(repr(~M), (I | M) & 6, I + 1, RegexFlag(10) is (I | M), repr(RegexFlag(1 << 20 | 2)))
