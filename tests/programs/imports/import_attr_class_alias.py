# A module-level name = m.C, of a class C through a module m's attribute, is an alias of the
# class (#804), as name = C after from m import C is: through import m, import m as n, a
# package's submodule, a module that a from-import binds and _thread.LockType (itself an alias of
# a class). Each is called, tested with isinstance(), annotated and its __name__ and a class
# attribute read, where it is bound and where another module from-imports it, also as an alias
# of an alias. An exception class's (Err) is a value, as it was, and so is a name that its module
# rebinds to an instance of its class (Gone).
import _thread
import mods.attralias_mid as mid
from mods.attralias_mid import Box, Crate, Again, Lock, made
from mods import attralias_shapes

B2 = mid.Box
B3 = B2


def show(label: str, b: Box) -> None:
    print(label, type(b).__name__, b.v, isinstance(b, Box), isinstance(b, Crate), isinstance(b, attralias_shapes.Box))


x: Box = Box(1)
c: Crate = Crate(2)
show("Box", x)
show("Crate", c)
show("Again", Again(3))
show("B2", B2(4))
show("B3", B3(5))
show("made", made())
print(Box.__name__, Crate.__name__, Again.__name__, B3.__name__, Box.kind, Crate.kind, B2.kind)
print(isinstance(_thread.allocate_lock(), Lock), Lock.__name__)
try:
    raise mid.Err("x")
except attralias_shapes.Oops as e:
    print("caught", type(e).__name__)
print(mid.Gone, type(mid.Gone).__name__)
