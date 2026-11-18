# error: @_simple_enum of a class is supported with the class of enum it makes, as @_simple_enum(IntEnum) (no boundary= or use_args=)
# CPython's re declares its flags so (printing 1)
import enum


@enum._simple_enum(enum.IntFlag, boundary=enum.KEEP)
class RegexFlag:
    A = 1


print(RegexFlag.A)
