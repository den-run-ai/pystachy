# Module-level aliases of classes through module attributes (#804), which another module
# from-imports: through import m, import m as n, a module that a from-import binds and a lib
# module's alias of its class (_thread.LockType); an exception class's stays a value, and so does
# a singleton's (class Missing: ..., then Missing = Missing(): the instance)
import _thread
import mods.attralias_shapes
import mods.attralias_shapes as sh
from mods import attralias_shapes

Box = mods.attralias_shapes.Box
Crate = sh.Crate
Again = attralias_shapes.Box
Lock = _thread.LockType
Err = sh.Oops
Gone = sh.Missing


def made() -> Box:
    return Box(6)
