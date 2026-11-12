# Bound methods of one object read through its primary base and through a trait that both define
# the method (their shared root does not) are equal, as CPython's are: the object's class has one
# method f either way. Bound to two objects, they differ.
class Root:
    pass


class Primary(Root):
    def f(self) -> int:
        return 1


class Trait(Root):
    def f(self) -> int:
        return 2


class Both(Primary, Trait):
    pass


b = Both()
c = Both()
p: Primary = b
t: Trait = b
u: Trait = c
print(p.f(), t.f(), p.f == t.f, t.f == p.f, p.f != t.f, p.f == u.f, b.f == t.f)
