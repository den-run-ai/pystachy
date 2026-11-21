# __getattr__ (#1536) in the kinds of class that may define it: a dataclass, a class with
# __slots__ (a slot that no code assigns reaches the method), an object that may be None
# (CPython's AttributeError names the attribute) and a union of classes with and without one.
from dataclasses import dataclass, field


@dataclass
class Settings:
    name: str
    values: dict[str, int] = field(default_factory=dict)
    hits: int = 0

    def __getattr__(self, key: str) -> int:
        self.hits += 1
        return self.values.get(key, -1)


st = Settings("s", {"port": 80})
print(st, st.port, st.depth, st.hits, st.name)
print(st == Settings("s", {"port": 80}, 2), getattr(st, "port", 0), hasattr(st, "anything"))


class Slotted:
    __slots__ = ("a", "b")

    def __init__(self) -> None:
        self.a = 1

    def __getattr__(self, name: str) -> int:
        return 100 + len(name)


sl = Slotted()
print(sl.a, sl.b, sl.c, hasattr(sl, "b"), hasattr(sl, "zz"), getattr(sl, "b", 0))
sl.a = 5
print(sl.a, sl.b)


class Conf:
    def __init__(self) -> None:
        self.data = {"port": 80}

    def __getattr__(self, name: str) -> int:
        return self.data[name]


def read(c: Conf | None) -> int:
    if c is None:
        return -1
    return c.port


def blind(c: Conf | None) -> int:
    return c.port


print(read(Conf()), read(None))
try:
    print(blind(None))
except AttributeError as e:
    print("AttributeError:", e)
try:
    print(Conf().nope)
except KeyError as e:
    print("KeyError:", e)


class Plain:
    def __init__(self) -> None:
        self.port = 1


def either(x: Conf | Plain) -> int:
    return x.port


def has(x: Conf | Plain, name: str) -> bool:
    return hasattr(x, name)


print(either(Conf()), either(Plain()), has(Conf(), "port"), has(Plain(), "port"), has(Plain(), "data"))
print(getattr(Conf(), "port", 0), getattr(Plain(), "port", 0), hasattr(Plain(), "nope"))
x = Conf()
if hasattr(x, "port"):
    print("port")
if hasattr(x, "data"):
    print("data")
