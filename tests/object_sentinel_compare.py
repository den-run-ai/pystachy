# object()'s object compared with == and != to values of builtin types (a range object and an
# iterator too), which are never equal to it (CPython compares them by identity, as neither type's
# __eq__ takes the other), and type(x) is object
_MISSING = object()


def seen(v):
    print("seen", v)
    return v


a = _MISSING
print(a == 1, 1 == a, a != 1, 1 != a)
print(a == "a", "a" == a, a != "a", "a" != a)
print(a == True, False == a, a == 1.5, 0.0 != a, a == b"x", b"x" != a)
print(a == [1], [2] == a, a == (1, "a"), (3,) != a, a == {1: "a"}, {"b": 2} != a, a == {1}, frozenset([1]) == a)
n: int | None = None
m: int | None = 3
print(a == n, n == a, a == m, m != a)
u: int | str = "a"
print(a == u, u != a)
print(seen(2) == a, a != seen("b"))
r = range(3)
it = iter([1, 2])
print(a == r, r == a, a != r, r != a, a == it, it != a)
print(a == None, None != a, a == a, a != a)

print(type(a) is object, a.__class__ is object, type(a) == object, type(a) is not object, object is type(a))
print(type(1) is object, type("s") == object, type(None) is object, type([1]) is not object)
print(type(a) is int, type(a) is type(1), type(a) is type(_MISSING))
