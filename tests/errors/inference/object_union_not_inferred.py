# error: expected int, got Meter
# No union with a class member is inferred: annotate the variable (total: int | Meter = 0),
# start from an object, or use sum().
class Meter:
    def __init__(self, n: int) -> None:
        self.n = n

    def __radd__(self, other: int) -> "Meter":
        return Meter(self.n + other)

    def __add__(self, other: "Meter") -> "Meter":
        return Meter(self.n + other.n)


def total(meters: list[Meter]) -> None:
    result = 0
    for meter in meters:
        result = result + meter
    print(result)


total([Meter(1)])
