# Dataclasses whose own __init__ assigns attributes that are no fields: neither the __init__
# @dataclass writes for a subclass, nor __repr__, __eq__ and replace() see them.
from dataclasses import dataclass, replace


@dataclass(init=False)
class Base:
    x: int

    def __init__(self, x: int) -> None:
        self.x = x
        self.extra = x * 10


@dataclass
class Derived(Base):
    y: int = 0


@dataclass
class Own:
    name: str

    def __init__(self, name: str) -> None:
        print("Own.__init__", name)
        self.name = name + "!"
        self.spaces: int = name.count(" ")


d = Derived(1, 2)
print(d, d == Derived(1, 2), d == Derived(1, 3))
try:
    print(d.extra)
except AttributeError as e:
    print("AttributeError", e)
b = Base(3)
print(b, b.extra, b == Base(3))
o = replace(Own("zoë"), name="ü n ï")
print(o, o.spaces, replace(d, y=5))
