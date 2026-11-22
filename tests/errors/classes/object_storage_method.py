# error: 'object' object has no method 'upper' (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise)
# a method of a value of object that isinstance() has not narrowed
x: object = "a"
print(x.upper())
