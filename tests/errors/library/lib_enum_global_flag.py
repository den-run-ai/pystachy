# error: @global_enum of flag class Perm is not supported
# CPython's repr() of a flag that @global_enum decorates names the module and the flag's
# members (printing __main__.R|__main__.W)
from enum import Flag, global_enum


@global_enum
class Perm(Flag):
    R = 4
    W = 2


print(repr(R | W))
