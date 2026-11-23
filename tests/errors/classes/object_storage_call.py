# error: 'object' object is not callable (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type, complex, range or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise; a test does not narrow a module's variable: test it in a function)
# a call of a value of object (its object may be a class, or an object whose class has __call__)
class C:
    pass


x: object = C
print(x())
