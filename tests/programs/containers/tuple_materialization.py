# Fresh fixed displays can construct the final runtime-length representation.
events: list[str] = []


def item(name: str, value: float) -> float:
    events.append(name)
    return value


def pair(x: float) -> tuple[float, ...]:
    return (x, x + 1.0)


def optional(x: float) -> tuple[float | None, ...]:
    return (item("first", x), item("second", x + 1.0), None)


def failure() -> float:
    events.append("raise")
    raise ValueError("later item")


def interrupted(x: float) -> tuple[float | None, ...]:
    return (item("before", x), failure(), item("after", x))


def copy_fixed(values: tuple[float, float]) -> tuple[float, ...]:
    return values


def strings(i: int) -> tuple[str | None, ...]:
    return ("first-" + str(i), None, "last-" + str(i))


def numeric_optional(x: float) -> tuple[float | None, ...]:
    return (x, None, x + 1.0)


def flags(b: bool) -> tuple[bool, ...]:
    return (b, not b)


class Derivatives:
    def __init__(self, values: tuple[float, ...]) -> None:
        self.values = values


def gradients(x: float, y: float) -> Derivatives:
    return Derivatives((y, x))


print(pair(2.5), optional(-0.0), events)
try:
    interrupted(3.0)
except ValueError as error:
    print(str(error), events)
source = (item("source", 2.0), 7.0)
held = [source]
converted = copy_fixed(source)
print(source, converted, held[0] is source)
print(flags(True), flags(False))
kept: list[tuple[str | None, ...]] = []
derivatives: list[Derivatives] = []
kept_numbers: list[tuple[float | None, ...]] = []
for i in range(40):
    kept.append(strings(i))
    derivatives.append(gradients(float(i), float(i + 1)))
    kept_numbers.append(numeric_optional(float(i)))
for i in range(100):
    garbage = ["collect-" + str(i), str(i) * 32]
print(kept[0], kept[-1], derivatives[0].values, derivatives[-1].values)
print(kept_numbers[0], kept_numbers[-1])
print(events)
