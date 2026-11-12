# A builtin number to an object's power calls the object's reflected method, as the other
# reflected arithmetic methods are called; an object that is None raises CPython's TypeError.
class Power:
    def __init__(self, n: int) -> None:
        self.n = n

    def __rpow__(self, other: int) -> int:
        print("  rpow", other)
        return other ** self.n


def missing() -> Power:
    return Power(1) if len("a") > 1 else None


print(2 ** Power(5), pow(3, Power(2)))
try:
    print(2 ** missing())
except TypeError as error:
    print("TypeError:", error)
