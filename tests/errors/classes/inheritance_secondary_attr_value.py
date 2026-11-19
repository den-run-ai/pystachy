# error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# A secondary base may declare an attribute (count: int), not bind a class attribute.
class Api:
    count: int = 0


class Base:
    pass


class C(Base, Api):
    pass
