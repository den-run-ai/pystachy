# error: exc_classvar_overridden_assign.py:10: error: assigning class attribute E.level is not supported where S binds 'level' in its class body too: an object's class attribute is read through the class of its static type (no dispatch on the object's class)
class E(Exception):
    level = 1


class S(E):
    level = 2


E.level = 9
e: E = S("z")
print(e.level)  # (CPython: 2, S's)
