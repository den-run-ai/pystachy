# Two secondary bases that each extend an interface of their own: an object of the class is of
# all four types, so isinstance() between the interfaces they extend tests the object's class, also
# where a subclass adds the second base or a third stands beside them.
class A:
    def a(self) -> str:
        return "a"


class R(A):
    def r(self) -> str:
        return "r"


class B:
    def b(self) -> str:
        return "b"


class S(B):
    def s(self) -> str:
        return "s"


class T:
    def t(self) -> str:
        return "t"


class P:
    def p(self) -> str:
        return "p"


class C(P, R, S):
    pass


class OnlyR(P, R):
    pass


class Low(OnlyR, S):
    pass


class Three(P, R, S, T):
    pass


def between(a: A, b: B) -> list[bool]:
    return [isinstance(a, B), isinstance(b, A), isinstance(a, S), isinstance(b, R), isinstance(a, P), isinstance(b, P), isinstance(a, T), isinstance(b, T)]


def cross(a: A) -> str:
    if isinstance(a, B):
        return a.b()
    return "not b"


def from_p(p: P) -> list[bool]:
    return [isinstance(p, A), isinstance(p, B), isinstance(p, R), isinstance(p, S)]


def from_t(t: T) -> list[bool]:
    return [isinstance(t, A), isinstance(t, B), isinstance(t, R), isinstance(t, S)]


c = C()
low = Low()
three = Three()
print(between(c, c), cross(c), cross(OnlyR()), cross(A()))
print(between(low, low), between(three, three), between(OnlyR(), low))
print(from_p(c), from_p(OnlyR()), from_p(low), from_p(P()), from_t(three), from_t(T()))
