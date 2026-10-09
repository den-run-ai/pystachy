# ... as a class body, or among its fields and methods, is a statement that does nothing, as pass.
class E(Exception):
    """doc"""
    ...


class F(E):
    ...


class P:
    x: int = 1
    ...


print(P().x)
try:
    raise F("z")
except E as e:
    print(repr(e))
raise E("y")
