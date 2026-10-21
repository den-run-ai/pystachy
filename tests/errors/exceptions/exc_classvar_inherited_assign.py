# error: exc_classvar_inherited_assign.py:10: error: assigning class attribute 'n' through S, which inherits it from E, is not supported (CPython would give S an attribute of its own; E.n = ... changes the one they share)
class E(Exception):
    n = 0


class S(E):
    pass


S.n = 1
print(S.n, S("x").n, E.n)  # (CPython: 1 1 0)
