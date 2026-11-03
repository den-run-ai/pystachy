# Base.__init__(self, ...) keeps its arguments as super().__init__(...) does; a subclass without
# an __init__ runs its base's, and one whose __init__ calls the base's through super() keeps what
# the base's call to its own builtin base keeps.
class Located(LookupError):
    def __init__(self, what: str, where: int) -> None:
        self.what = what
        self.where = where
        LookupError.__init__(self, what + " at " + str(where))


class Missing(Located):
    pass


class Deep(Located):
    def __init__(self, what: str, where: int, depth: int) -> None:
        self.depth = depth
        super().__init__(what, where + depth)


a = Located("key", 3)
print(str(a), repr(a), a.what, a.where)
b = Missing("name", 5)
print(str(b), repr(b), b.what, b.where)
c = Deep("path", 1, 2)
print(str(c), repr(c), c.what, c.where, c.depth)
try:
    raise Deep("x", 0, 1)
except Located as err:
    print("caught", err, repr(err))
