# error: unsupported call sum(list[Meter]): its first addition is 0 + Meter, which needs Meter.__radd__; or give it a start to add to, as in sum(items, start)
class Meter:
    def __init__(self, n: int) -> None:
        self.n = n

    def __add__(self, other: "Meter") -> "Meter":
        return Meter(self.n + other.n)


print(sum([Meter(1), Meter(2)]))
