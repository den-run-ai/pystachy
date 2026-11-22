# error: comparing values of object with < is not supported: their objects' classes are known only when the program runs (compare with ==, != or is) (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# ordering a value of object (== and != compare it with any value)
x: object = 1
print(x < 2)
