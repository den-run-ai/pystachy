# error: reflection of a value of object is not supported: its object's class is known only when the program runs (#487) (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# type() of a value of object as a value (type(x).__name__ is supported)
x: object = 1
print(type(x))
