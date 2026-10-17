# an export that hands control to a Python loop, which calls another export back many times: the
# Objects each callback drops are released during the loop, not when the outer call returns
from ffi import export
from pyobj import import_module, of_int


@export
def handler(i: int) -> int:
    b = import_module("builtins").attr("bytearray").call([of_int(1 << 20)])
    return len(b) + i


@export
def serve(n: int) -> int:
    return import_module("evl_loop").attr("run").call([of_int(n)]).to_int()
