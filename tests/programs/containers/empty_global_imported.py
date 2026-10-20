# An empty container that from m import X copies, filled by the importer, by the importer's
# function or by m's function: the copy and the module's global hold the same container,
# and the first fill of either gives both its type.
from infer.reg import REG, ITEMS, NAMES, name, dump
from infer.reg import ALIASED as AL
import infer.reg as reg

REG["a"] = 1
print(REG, reg.REG)


def add(x: str) -> None:
    ITEMS.append(x)


print(len(ITEMS))
add("x")
print(ITEMS)
name("n", 1)
name("n", 2)
print(NAMES)
AL["k"] = 2.5
print(AL, reg.ALIASED)
dump()
