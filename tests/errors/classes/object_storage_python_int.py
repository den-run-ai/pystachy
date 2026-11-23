# error: unsupported operand type(s) for +: 'object' and 'int' (narrow a value of object with isinstance() to float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first, not to int in a module that opts in to promoting ints
# pystachy: python-int
# isinstance(x, int) narrows nothing in a module that opts in to promoting ints: a bool passes the
# test, which the promoting int that x would be cannot hold
x: object = 1
if isinstance(x, int):
    print(x + 1)
