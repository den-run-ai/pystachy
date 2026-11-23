# error: unsupported operand type(s) for +: 'object' and 'int' (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type, complex, range or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise; a test does not narrow a module's variable: test it in a function)
# arithmetic on a value of object that isinstance() has not narrowed: its object's type is known
# only when the program runs (as for its attributes, calls, indexing and iteration)
x: object = 1
print(x + 1)
