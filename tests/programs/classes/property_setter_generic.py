# The fields a property's setter assigns where __init__ calls it are the class's: also in a
# generic class, typed as its specialization's type variables, and through a setter that
# assigns another property (or its own) in turn.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    @property
    def v(self) -> T:
        return self._v

    @v.setter
    def v(self, x: T) -> None:
        self._v = x
        self.sets = 1


b = Box(1)
b.v += 41
s = Box("é")
s.v = s.v * 2
print(b.v, s.v, b.sets)


class Pair(Generic[T]):
    def __init__(self, a: T, b: T) -> None:
        self.first = a
        self.items = [a, b]

    @property
    def first(self) -> T:
        return self._first

    @first.setter
    def first(self, x: T) -> None:
        self._first = x
        self.history = [x]


p = Pair(2.5, 3.5)
p.first = 1.0
q = Pair(["a"], ["b"])
print(p.first, p.items, p.history, q.first, q.history)


class Temperature:
    def __init__(self, celsius: float) -> None:
        self.celsius = celsius

    @property
    def celsius(self) -> float:
        return self.kelvin - 273.15

    @celsius.setter
    def celsius(self, c: float) -> None:
        self.kelvin = c + 273.15

    @property
    def kelvin(self) -> float:
        return self._k

    @kelvin.setter
    def kelvin(self, k: float) -> None:
        if k < 0:
            raise ValueError("below absolute zero")
        self._k = k


t = Temperature(25.0)
print(t.kelvin, t.celsius)
try:
    Temperature(-300.0)
except ValueError as e:
    print("ValueError", e)


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    @property
    def n(self) -> int:
        return self._n

    @n.setter
    def n(self, v: int) -> None:
        if v > 3:
            print("down from", v)
            self.n = v - 1
        else:
            self._n = v


print(Countdown(5).n)
