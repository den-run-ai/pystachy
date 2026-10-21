# A return annotation names a specialization of an imported module's generic class, whose methods
# are compiled while the program's declarations are read: a call there that leaves out a default
# argument (Bag() in __neg__) takes the default from the frame of its module.
from mods.gbag import Bag


def make() -> Bag[str]:
    return Bag("ab")


print((-make()).items, (-Bag([1, 2, 3])).items, (-Bag[float]()).items)
