# error: reflection of a value of object is not supported: its object's class is known only when the program runs (#487) (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type, complex, range or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise; a test does not narrow a module's variable: test it in a function)
# type() of a value of object as a value (type(x).__name__ is supported)
x: object = 1
print(type(x))
