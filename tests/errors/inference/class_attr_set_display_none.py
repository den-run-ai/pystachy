# error: cannot infer the type of class attribute 'NAMES'; annotate it (NAMES: T = ...)
# None types no set: an element cannot be None.
class Table:
    NAMES = {None, "a"}


print(len(Table.NAMES))
