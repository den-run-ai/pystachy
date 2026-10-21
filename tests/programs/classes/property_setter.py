# Property setters and deleters: assignment, augmented assignment and del call them; a
# property without one raises CPython's AttributeError when it runs.


def trace(label: str, v: float) -> float:
    print("eval", label)
    return v


class Temperature:
    def __init__(self, celsius: float) -> None:
        self.celsius = celsius  # (the setter assigns _celsius: a field of the class)
        self.history: list[float] = []

    @property
    def celsius(self) -> float:
        print("get celsius")
        return self._celsius

    @celsius.setter
    def celsius(self, value: float) -> None:
        print("set celsius", value)
        if value < -273.15:
            raise ValueError("below absolute zero")
        self._celsius = value

    @celsius.deleter
    def celsius(self) -> None:
        print("delete celsius")
        self._celsius = 0.0

    @property
    def fahrenheit(self) -> float:
        return self.celsius * 9.0 / 5.0 + 32.0

    @fahrenheit.setter
    def fahrenheit(self, value: float) -> int:
        self.celsius = (value - 32.0) * 5.0 / 9.0
        return 99  # (CPython ignores what a setter returns)

    @property
    def kelvin(self) -> float:
        return self._celsius + 273.15

    def reset(self) -> None:
        self.celsius = 0.0
        del self.celsius


def holder(t: Temperature) -> Temperature:
    print("eval holder")
    return t


t = Temperature(21.5)
print(t.celsius)
t.celsius = 30.0
t.fahrenheit = 212.0
print(t.celsius, t.fahrenheit)
holder(t).celsius = trace("value", 10.0)
holder(t).celsius += trace("increment", 2.5)
print(t.celsius)
t.celsius -= 2.0
t.celsius *= 2.0
print(t.celsius)
del t.celsius
print(t.celsius)
t.reset()
a = Temperature(1.0)
a.celsius = t.celsius = 5.0
print(a.celsius, t.celsius)
a.celsius, t.celsius = 7.0, 8.0
print(a.celsius, t.celsius)
try:
    t.celsius = -300.0
except ValueError as e:
    print("caught", e)
print(t.celsius)

# no setter or deleter: AttributeError, after the value and the object are evaluated
try:
    holder(t).kelvin = trace("kelvin", 3.0)
except AttributeError as e:
    print("caught", e)
try:
    t.kelvin += 1.0
except AttributeError as e:
    print("caught", e)
try:
    del t.kelvin
except AttributeError as e:
    print("caught", e)
try:
    del t.fahrenheit
except AttributeError as e:
    print("caught", e)

missing: Temperature | None = None
try:
    missing.celsius = trace("none", 1.0)
except AttributeError as e:
    print("caught", e)
try:
    del missing.celsius
except AttributeError as e:
    print("caught", e)


def announce(what: str) -> int:
    print("default of", what)
    return 0


class Counter:
    def __init__(self) -> None:
        self._n = 0
        self.items: list[str] = []

    @property
    def n(self) -> int:
        return self._n

    @n.setter
    def n(self, value: int = announce("the setter")) -> None:  # (evaluated as the def runs)
        self._n = value

    @property
    def tags(self) -> list[str]:
        return self.items

    @tags.setter
    def tags(self, value: list[str]) -> None:
        self.items = value


def bump(o):
    o.n += 1
    return o.n


def nested() -> int:
    c = Counter()

    def inc(k: int) -> None:
        c.n = c.n + k

    inc(3)
    inc(4)
    return c.n


c = Counter()
for i in range(3):
    c.n += i
print(c.n, bump(c), nested())
c.tags = []
c.tags.append("é")
c.tags += ["ü"]
print(c.tags, c.items)
t.kelvin = 1.0
print("not reached")
