# error: 'object' object is not iterable (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type, complex, range or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise; a test does not narrow a module's variable: test it in a function)
# iterating over a value of object that isinstance() has not narrowed
x: object = [1, 2]
for i in x:
    print(i)
