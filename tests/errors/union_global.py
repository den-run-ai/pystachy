# error: union_global.py:8: error: + of a value of int | str is not supported: copy it to a local variable, and narrow that to one of its types with isinstance() (a test does not narrow a global or a field, which a call may change)
# a test does not narrow a global (or a field)
g: int | str = 1


def bump() -> int:
    if isinstance(g, int):
        return g + 1
    return 0


print(bump())
