# error: nonmember() in a class that @_simple_enum makes is not supported (CPython's makes the nonmember object a member's value)
# CPython's _simple_enum reads the class's own namespace, which does not unwrap nonmember(): X is
# a member whose value is the nonmember object (printing 2 members)
import enum
from enum import Enum, nonmember


@enum._simple_enum(Enum)
class C:
    A = 1
    X = nonmember(2)


print(len(C))
