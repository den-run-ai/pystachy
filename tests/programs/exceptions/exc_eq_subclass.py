# == and the other comparisons of a value typed by an exception class run the methods of the
# object's own class, which a subclass may define (#135), as they do for ordinary classes.
class E(Exception):
    pass


class F(E):
    def __eq__(self, other: object) -> bool:
        print("F.__eq__", str(self))
        return True


class G(F):
    pass


class H(E):
    pass


class Ne(E):
    def __ne__(self, other: object) -> bool:
        print("Ne.__ne__", str(self))
        return False


class Lt(E):
    def __lt__(self, other: E) -> bool:
        return True


class Unmade(E):
    def __eq__(self, other: object) -> bool:
        return True


def eq(x: E, y: E) -> bool:
    return x == y


def ne(x: E, y: E) -> bool:
    return x != y


def lt(x: E, y: E) -> bool:
    return x < y


def is_none(x):
    return x == None


e = E("e")
f = F("f")
g = G("g")
h = H("h")
print(eq(f, e), eq(e, f), eq(e, e), eq(e, h), eq(h, g), eq(g, f))
print(ne(f, e), ne(e, f), ne(e, h), ne(Ne("n"), e), ne(e, Ne("m")))
print(f == None, None == f, f != None, e == None, is_none(f), is_none(e))
o: E | None = None
print(o == f, f == o, o != e, e != o, o == o)
o = g
print(o == e, e == o)
hh: H = H("x")
print(hh == f, f == hh, hh != f, hh == e)
xs: list[E] = [e, h, f]
print(g in xs, xs.index(g), xs.count(g), h in xs, xs.count(h))
print(e in (h, f), (f, 1) == (e, 1), [e] != [f])
print(lt(Lt("a"), e))
try:
    print(lt(e, Lt("b")))
except TypeError as err:
    print("TypeError:", err)
try:
    raise G("raised")
except E as caught:
    print(caught == e, caught != e)


class P(Exception):
    def __eq__(self, other: "P") -> bool:
        print("P.__eq__", str(self), str(other))
        return False


class Q(P):
    pass


p = P("p")
q = Q("q")
print(p == q, q == p, p != q)  # (a subclass's object, on the right, compares first)


class Base:
    pass


class Sub(Base):
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: "Sub") -> bool:
        return self.n == other.n

    def __repr__(self) -> str:
        return f"Sub({self.n})"


s = Sub(1)
d: dict[str, Base] = {"k": s}
print(s == Sub(1), s != Sub(1), d)  # (d's helpers compare Bases, which Sub.__eq__ cannot take)


class Pr(Exception):
    pass


class Narrow(Pr):
    def __eq__(self, other: "Narrow") -> bool:
        return True


gs: list[Pr] = [Narrow("h"), Pr("g")]
print(gs, len(gs), gs[0] is gs[0])  # (gs's helpers compare Prs, which Narrow.__eq__ cannot take)
