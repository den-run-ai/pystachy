# A class-body default is a class attribute, which an object reads until it assigns its own:
# calling __init__ again (o.__init__(), through a bound method, from another class's method)
# sees what the object holds, not the default. A dataclass's own __init__ assigns every field.
from dataclasses import dataclass


class Counter:
    value: int = 0
    tags: list[str] = []
    limit: int = len("abcd")

    def __init__(self) -> None:
        self.value += 1
        self.tags = self.tags + ["t"]
        self.limit -= 1


c = Counter()
print(c.value, c.tags, c.limit)
c.__init__()
print(c.value, c.tags, c.limit)
f = c.__init__
f()
print(c.value, c.tags, c.limit, Counter().value, Counter.tags)


class Other:
    def reset(self, c: Counter) -> None:
        c.__init__()


Other().reset(c)
print(c.value, len(c.tags))


class Plain:
    a: int = 5
    b: str = "x"


p = Plain()
p.a = 6
p.__init__()
print(p.a, p.b, Plain().a)


class Shared:
    total: int = 0
    mine: int = 0

    def __init__(self) -> None:
        self.mine += 1
        Shared.total += 1


s = Shared()
s.__init__()
print(s.mine, Shared.total, s.total, Shared().mine)


class Box:
    k: int = 100

    def __init__(self, v):
        self.v = v
        self.k += 1


b = Box(3)
b.__init__(4)
print(b.k, b.v, Box("s").k)


@dataclass
class Point:
    x: int = 1
    y: int = 2


d = Point(10, 20)
d.__init__()
print(d)
d.__init__(y=7)
print(d)


@dataclass
class Scaled:
    x: int = 1
    y: int = 0

    def __post_init__(self) -> None:
        self.y += self.x * 2


sc = Scaled(5)
print(sc)
sc.__init__(3, 1)
print(sc)


@dataclass
class Own:
    n: int = 0

    def __init__(self) -> None:
        self.n += 1


o = Own()
o.__init__()
print(o.n, o)


class Err(Exception):
    count: int = 0

    def __init__(self) -> None:
        self.count += 1


e = Err()
e.__init__()
print(e.count)


class Base(Exception):
    hits: int = 0

    def __init__(self) -> None:
        self.hits += 1


class Sub(Base):
    def __init__(self) -> None:
        super().__init__()
        Base.__init__(self)


x = Sub()
x.__init__()
print(x.hits)
