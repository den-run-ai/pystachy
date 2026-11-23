# error: unsupported operand type(s) for +: 'object' and 'int' (narrow a value of object with isinstance() to float, bool, str, bytes, list, tuple, dict, set, frozenset, type, complex, range or a class of the program first, not to int in a module that opts in to promoting ints: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise; a test does not narrow a module's variable: test it in a function)
# pystachy: python-int
# isinstance(x, int) narrows nothing in a module that opts in to promoting ints: a bool passes the
# test, which the promoting int that x would be cannot hold
x: object = 1
if isinstance(x, int):
    print(x + 1)
