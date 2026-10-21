# Dataclasses ordered by fields that are dataclasses, with property setters, and frozen
# dataclasses, whose __setattr__ raises before a property's setter runs.
from dataclasses import FrozenInstanceError, dataclass, field


@dataclass(order=True)
class Version:
    major: int
    minor: int = 0


@dataclass(order=True)
class Release:
    version: Version
    tags: list[str] = field(default_factory=list)
    name: str = ""


rs = [Release(Version(1, 2), ["b"]), Release(Version(1, 2), ["a"]), Release(Version(0, 1), name="z")]
print(sorted(rs))
print(rs[0] > rs[1], rs[2] < rs[0])


@dataclass
class Temperature:
    _c: float = 0.0

    @property
    def c(self) -> float:
        return self._c

    @c.setter
    def c(self, v: float) -> None:
        print("set", v)
        self._c = v


t = Temperature()
t.c = 3.5
t.c += 1.0
print(t, t.c)


@dataclass(frozen=True)
class Locked:
    _c: float = 0.0

    @property
    def c(self) -> float:
        return self._c

    @c.setter
    def c(self, v: float) -> None:
        print("never", v)


lk = Locked(2.0)
try:
    lk.c = 1.0
except FrozenInstanceError as e:
    print("frozen", e)
try:
    lk.c += 1.0
except FrozenInstanceError as e:
    print("frozen", e)
try:
    del lk.c
except AttributeError as e:
    print("frozen", e)
print(lk.c)


@dataclass(order=True, frozen=True)
class Empty:
    pass


print(Empty() < Empty(), Empty() <= Empty(), Empty() == Empty())
