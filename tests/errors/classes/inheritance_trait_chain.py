# error: inheritance_trait_chain.py:23: error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# A trait (a fieldless secondary base whose base is a class of the primary base's chain) derives
# from that class directly: through another class (Ancestor), isinstance() and Ancestor's methods
# would not know the objects of a class that derives from both.
class Root:
    pass


class Primary(Root):
    pass


class Ancestor(Root):
    def g(self) -> int:
        return 7


class Trait(Ancestor):
    def h(self) -> int:
        return 8


class Both(Primary, Trait):
    pass


b = Both()
print(isinstance(b, Ancestor), b.g(), b.h())
