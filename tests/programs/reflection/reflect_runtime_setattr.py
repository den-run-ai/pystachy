# setattr(o, name, value) with a name read at run time (#489's first version), where __slots__
# closes the names of o's class: a slot field stores the value, a property calls its setter, and
# every other name raises CPython's error
class P:
    __slots__ = ("x", "y", "_t")

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self._t = 0

    def norm(self) -> int:
        return self.x * self.x + self.y * self.y

    @property
    def t(self) -> int:
        return self._t

    @t.setter
    def t(self, v: int) -> None:
        print("setter", v)
        self._t = v

    @property
    def ro(self) -> int:
        return 1


class Q(P):
    __slots__ = ("w",)

    def __init__(self) -> None:
        super().__init__(0, 0)
        self.w = 0


p = P(1, 2)
for name in input().split():
    try:
        setattr(p, name, 5)
        print(name, "set")
    except AttributeError as e:
        print(name, "AttributeError:", e)
    except TypeError as e:
        print(name, "TypeError:", e)
print(p.x, p.y, p.t)
objs: list[P] = [P(3, 4), Q()]
for o in objs:
    for n in ["x", "w"]:
        try:
            setattr(o, n + "", 7)
        except AttributeError as e:
            print("AttributeError:", e)
    print(o.x)
