# A module's alias of a function or class it from-imports (name = f) is from-imported in turn
# (#159): by name and with as, by import *, in a function, as an alias of an alias, from a
# package (pylev's levenshtein = wfi_levenshtein) and in an import cycle; each is the function
# or class itself, as import m and m.name have it
from mods.alias_mid import plus_one, Crate, also
from mods.alias_mid import plus_one as po
from mods.alias_chain import again
from mods.aliaspkg import double
from mods.aliaspkg import *
import mods.alias_cyc_a
import mods.alias_mid
import mods.alias_base


def late(x: int) -> int:
    from mods.alias_chain import again as a2
    return a2(x)


print(plus_one(1), po(2), also(3), again(4), double(5), twice(6), late(10))
c = Crate(7)
print(c.v, isinstance(c, mods.alias_base.Box), mods.alias_mid.plus_one(8), mods.alias_mid.Crate(9).v)
print(mods.alias_cyc_a.first(1))
