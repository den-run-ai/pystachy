# __getattr__ (#1536) with class objects and joined classes: an object made through a type[C]
# value, o.__class__ or type(o) reads as one made by C(), its class's attributes are its
# class's (the class object asks no __getattr__), and a value joined from related classes
# reads through their common class. A base without the method reads a field that every object
# assigns as it does without one.
class Conf:
    limit = 3

    def __init__(self) -> None:
        self.data = {"port": 80}

    def __getattr__(self, name: str) -> int:
        return self.data.get(name, -1)


class Sub(Conf):
    pass


class Plain:
    def __init__(self) -> None:
        self.n = 5


class Lazy(Plain):
    def __getattr__(self, name: str) -> int:
        return -len(name)


def make(t: type[Conf]) -> Conf:
    return t()


t: type[Conf] = Conf
o = t()
print(o.port, t.limit, type(o).__name__, o.__class__.__name__)
print(make(Sub).port, make(Conf).depth)
k = o.__class__
print(k().port, k.limit)


def pick(flag: bool) -> None:
    y = Sub() if flag else Conf()
    print(y.port, y.abc)
    z = Lazy() if flag else Plain()
    print(z.n)
    w = [Sub(), Conf()]
    print([v.port + v.xy for v in w])


pick(True)
pick(False)
