# Two except clauses bind one name to objects of a class and of a class deriving from it: each
# clause's name has the type of its own clause (the second reads the subclass's field), and both
# are unbound after their clause.
class A(Exception):
    pass


class B(A):
    def __init__(self, x: int):
        super().__init__(x)
        self.x = x


def f() -> None:
    try:
        raise B(1)
    except A as e:
        print("A", e)
    try:
        raise B(2)
    except B as e:
        print(e.x)
    try:
        print(e)
    except UnboundLocalError:
        print("unbound")


f()
e = A("q")
print(e)
try:
    raise B(3)
except B as e:
    print(e.x, repr(e))
try:
    print(e)
except NameError:
    print("unbound")
