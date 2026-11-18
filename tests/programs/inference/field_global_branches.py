# A field stored from a module global that each branch of a module-level if statement binds, to
# values of one type, takes that type, as mypyc's RVec stores self.types =
# [c_pyssize_t_rprimitive, pointer_rprimitive], where rtypes.py binds c_pyssize_t_rprimitive under
# if IS_32_BIT_PLATFORM: and under else:. So does one that module code binds again to a value of
# that type.
import sys


class RPrimitive:
    def __init__(self, name: str, size: int) -> None:
        self.name = name
        self.size = size


IS_32_BIT = sys.maxsize < (1 << 31)
if IS_32_BIT:
    ssize = RPrimitive("int32_t", 4)
    WIDTH = 32
elif sys.maxsize < 0:
    ssize = RPrimitive("never", 0)
    WIDTH = 0
else:
    ssize = RPrimitive("int64_t", 8)
    WIDTH = 64
pointer = RPrimitive("void*", 8)
SCALE = 2


class RVec:
    def __init__(self) -> None:
        self.types = [ssize, pointer]
        self.width = WIDTH
        self.first = ssize
        self.scale = SCALE


print(RVec().scale)
SCALE = 3
v = RVec()
print([t.name for t in v.types], v.width, v.first.size, v.scale)
v.types.append(RPrimitive("char", 1))
print(len(v.types), v.types[-1].size)
