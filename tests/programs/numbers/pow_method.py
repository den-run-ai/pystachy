# An object to an object's power is its __pow__, as a + b is its __add__; a number exponent
# and a number base (the reflected method) are called too.
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"V({self.n})"

    def __pow__(self, k: "V | int") -> "V":
        if isinstance(k, V):
            print("  pow V")
            return V(self.n ** k.n)
        print("  pow int")
        return V(self.n ** k)

    def __rpow__(self, k: int) -> "V":
        print("  rpow", k)
        return V(k ** self.n)


def missing() -> V:
    return V(1) if len("a") > 1 else None


print((V(3) ** V(2)).n, pow(V(2), V(3)), V(2) ** 5, pow(V(2), 3), 2 ** V(5), pow(3, V(2)))
power = V(2)
power **= 3
print(power)
power **= V(2)
print(power)
try:
    print(V(2) ** missing())
except TypeError as error:
    print("TypeError:", error)
