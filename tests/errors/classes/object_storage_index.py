# error: 'object' object is not subscriptable (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# indexing a value of object that isinstance() has not narrowed
x: object = [1, 2]
print(x[0])
