# error: lib_enum_int_param_method.py:13: error: 'Color' object has no method 'to_bytes' (compiling pack(Color) for the call at
# A member passed for a parameter annotated int compiles the function for the member's class, as
# CPython passes it on (#1394): an int method that the member does not have here is an error that
# names the call and the parameter (CPython prints b'\x00\x01').
from enum import IntEnum


class Color(IntEnum):
    RED = 1


def pack(n: int) -> bytes:
    return n.to_bytes(2, "big")


print(pack(Color.RED))
