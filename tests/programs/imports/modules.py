# Importing Python modules: packages, submodules, relative and circular imports, the order in
# which module code runs, from-imports (which copy a variable's current value), star imports
# with __all__, module attributes read and assigned, and classes used across modules.
print("main: start")
import mods.counter
from mods import counter as c2
from mods.counter import count, incr, LIMIT
import mods.shapes as sh
from mods.shapes import *
from mods import cyc_a
import mods.ns.leaf


def helper() -> str:
    return "main.helper"


x = "main x"
print(mods.VERSION, mods.counter.LIMIT, c2.LIMIT, LIMIT)
print(helper(), sh.helper(), x, sh.x, __name__)
print(incr(2), incr(2), mods.counter.count, count, c2.count)
print(mods.counter.describe())
mods.counter.LIMIT = 10
print(incr(5), c2.describe(), LIMIT)


def late() -> int:
    from mods.counter import count
    return count


print(late(), count)
sq = [Square(3), sh.Square(1), mods.Square(2)]
print(sq, sorted(sq), biggest(sq), area(sq[0]), mods.area(sq[1]))
print(Square(2) == sh.Square(2), Square(2) in sq, sq.index(Square(1)))
circles = {"a": Circle(1.0), "b": sh.Circle(2.5)}
print(circles, sh.circle_area(circles["b"]))
o = sh.Opaque()
print(repr(o).startswith("<mods.shapes.Opaque object at 0x"), o.v)
print(cyc_a.fa(1), cyc_a.AB, mods.cyc_b.B)
print(mods.ns.leaf.where())


def total(xs: list[sh.Square]) -> int:
    return sum([area(s) for s in xs])


print(total(sq))
