# error: cannot infer the type of class attribute 'STEPS'; annotate it (STEPS: T = ...)
# A float is no set element, so the display types nothing.
class Table:
    STEPS = {0.5, 1.5}


print(len(Table.STEPS))
