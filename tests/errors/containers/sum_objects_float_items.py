# error: sum() of Meter | float is not supported: CPython adds the floats with compensation until the first object; add the items in a loop, or sum the floats and the objects apart
# CPython's sum() adds floats with a compensated sum, from a float start or the first float
# after ints until the first object: sum([1e16, 1.0, -1e16], 0.0) is 1.0, not the 0.0 that
# adding them one by one gives. A sum of objects adds one by one, so floats beside objects
# are rejected rather than summed differently.
class Meter:
    def __init__(self, n: float) -> None:
        self.n = n

    def __radd__(self, other: float) -> "Meter":
        return Meter(other + self.n)


def total(items: "list[float | Meter]") -> "float | Meter":
    return sum(items, 0.0)


print(total([1e16, 1.0, -1e16]))
