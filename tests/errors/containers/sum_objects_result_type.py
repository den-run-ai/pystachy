# error: expected Meter, got Meter | int
# sum() of no items is the int 0: give it a start (sum(meters, Meter(0))) for a Meter result.
class Meter:
    def __init__(self, n: int) -> None:
        self.n = n

    def __radd__(self, other: int) -> "Meter":
        return Meter(self.n + other)

    def __add__(self, other: "Meter") -> "Meter":
        return Meter(self.n + other.n)


def total(meters: list[Meter]) -> Meter:
    return sum(meters)


print(total([Meter(1)]).n)
