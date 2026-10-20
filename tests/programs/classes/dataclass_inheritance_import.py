# Dataclasses deriving from another module's dataclasses: defaults the base's class statement
# evaluated once, an __init__ of the subclass's own that calls the base's, and init=False.
from dataclasses import FrozenInstanceError, dataclass, field

import dataclass_inheritance_mod
from dataclass_inheritance_mod import Event, Timed

print("imported")


@dataclass(frozen=True)
class Alarm(dataclass_inheritance_mod.Timed):
    weight: int = dataclass_inheritance_mod.counted("alarm weight")
    loud: bool = True


@dataclass(frozen=True, init=False)
class Silent(Timed):
    def __init__(self, name: str) -> None:
        super().__init__(name, 1, [], 0.5)
        print("Silent.__init__", self.name)


@dataclass(init=False)
class Plain:
    a: int = 1
    b: str = field(default="b", compare=False)


@dataclass(init=False)
class Sub(Plain):
    c: float = 2.0


events: list[Event] = [Event("e"), Timed("t", seconds=1.5), Alarm("a"), Silent("s"), Timed("t", 0, [], 1.5)]
for e in events:
    print(e, e.weight, e.notes)
print(events[1] == events[4], events[1] == Timed("t", seconds=1.5), events[3] == Silent("s"))
try:
    events[2].name = "x"
except FrozenInstanceError as err:
    print("FrozenInstanceError", err)
try:
    del events[3].name
except AttributeError as err:
    print("AttributeError", err)


def heaviest(es: list[Event]) -> Event:
    best = es[0]
    for e in es:
        if e.weight > best.weight:
            best = e
    return best


print(heaviest(events))
x = Sub()
print(x, x == Sub(), x.a, x.b, x.c)
