# An exception class whose body binds __module__ to a type other than str keeps a class variable,
# assigned and read as others are (CPython's __module__ is an ordinary class attribute), declared
# (__module__: int = 1) or not (__module__ = 5); one of str is the module the class shows, as an
# undeclared one is
class Coded(Exception):
    __module__: int = 1


class Bare(Exception):
    __module__ = 5


class Named(Exception):
    __module__: str = "m"


Coded.__module__ = 2
print(Coded.__module__, Coded().__module__)
Coded.__module__ += 3
print(Coded.__module__, Coded().__module__)
Bare.__module__ = 6
print(Bare.__module__, Bare().__module__)
print(Named.__module__, Named().__module__, repr(Named))
Named.__module__ = "n"
print(Named.__module__, Named().__module__, repr(Named))
