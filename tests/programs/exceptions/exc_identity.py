# Exceptions compare by identity, and an exception that raises an object of an exception class
# is that object: `e is x` after `raise x`, two catches of one raised object, == between objects
# of different exception classes (one deriving from the other), and lists of exceptions.
class A(Exception):
    pass


class B(A):
    pass


x = A("1")
y = B("2")
print(x == y, x != y, x is y, x is not y)
try:
    raise x
except Exception as e:
    print(e is x, e is not x, e == x, x == e, e != x)
errs: list[Exception] = []
for o in [y, y]:
    try:
        raise o
    except Exception as e:
        errs.append(e)
        print(e == y, y == e, e is y, e != x)
print(errs[0] is errs[1], errs[0] == errs[1], errs)
print(errs[0] in errs[1:], errs.index(errs[1]), errs.count(errs[0]), [errs[0]] == [errs[1]])
v = ValueError("q")
try:
    raise v
except ValueError as f:
    print(f is v, f == v, f == ValueError("q"))
try:
    raise A("first")
except A as e1:
    first = e1
    try:
        raise
    except Exception as e2:
        print(e2 is first, e2 == first)
