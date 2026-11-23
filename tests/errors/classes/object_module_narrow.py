# error: 'object' object has no attribute 'n' (narrow a value of object with isinstance() to int, float, bool, str, bytes, list, tuple, dict, set, frozenset, type, complex, range or a class of the program first: it takes only str(), repr(), format(), hash(), len(), int(), float(), % formatting, ==, !=, is, isinstance() and a truth test otherwise; a test does not narrow a module's variable: test it in a function)
# a test at a module's level narrows none of its variables, a value of object's as a union's
# (object_storage_narrow.py: in a function, it narrows)
class B:
    def __init__(self, n: str) -> None:
        self.n = n


o: object = B("g")
if isinstance(o, B):
    print(o.n)
