# Decorators across modules: an imported module's decorated defs, and the program's own defs
# decorated by what the module defines, through a from-import, an alias and a dotted name
import mods.decomod
from mods import decomod as dm
from mods.decomod import REGISTRY, add, neg, register

print("imported")


@register("main")
def three() -> int:
    return 3


@mods.decomod.trace
def sq(x):
    return x * x


@dm.register("aliased")
@dm.trace
def four(x: int) -> int:
    return x + 4


print(REGISTRY)
print(add(1, 2), neg(5), three(), sq(4), four(0), dm.twice_add(4), mods.decomod.add("a", "b"))
