# Nested entries: Python -> outer() -> Python (reent_cb) -> inner() -> pyobj calls, with Objects
# dropped all along (temporary receivers), so collections and releases happen in nested entries
from ffi import export
from pyobj import import_module, of_int


@export
def inner(n: int) -> int:
    s = 0
    for k in range(20):
        s += of_int(n + k).to_int()  # dropped without close()
    return s


@export
def outer(n: int) -> int:
    t = 0
    for i in range(n):
        cb = import_module("reent_cb")
        t += cb.attr("make").call([]).call([of_int(i)]).to_int()  # a fresh closure, held only by a temporary
        t += cb.attr("Box").call([])[of_int(i)].to_int()  # __getitem__ of a temporary calls back in
    return t
