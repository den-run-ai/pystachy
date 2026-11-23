# error: comparing values of object with < is not supported: their objects' classes are known only when the program runs (compare with ==, != or is) (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type, complex, range or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise; a test does not narrow a module's variable: test it in a function)
# ordering a value of object (== and != compare it with any value)
x: object = 1
print(x < 2)
