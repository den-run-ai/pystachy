# in, count() and index() of a tuple of complex numbers with an object whose class defines __eq__:
# complex's __eq__ declines it (CPython's returns NotImplemented), so the object's answers
class Match:
    def __eq__(self, other: complex) -> bool:
        return True


class Plain:
    pass


m = Match()
p = Plain()
t = (1j, 2j)
print(m in t, t.count(m), t.index(m), 1j in (m,), (m, p).count(1j))
print(p in t, t.count(p), 1j in (p,), "a" in (1j,), 1j in ("a", 2))
