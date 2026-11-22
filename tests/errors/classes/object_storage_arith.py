# error: unsupported operand type(s) for +: 'object' and 'int' (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# arithmetic on a value of object that isinstance() has not narrowed: its object's type is known
# only when the program runs (as for its attributes, calls, indexing and iteration)
x: object = 1
print(x + 1)
