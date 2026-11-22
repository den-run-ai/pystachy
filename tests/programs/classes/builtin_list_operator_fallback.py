class Added(list[int]):
    def __add__(self, other: list[int]) -> list[int]:
        return [99] + other


class Scaled(list[int]):
    def __rmul__(self, other: int) -> list[int]:
        return [42, other]


a = Added([1, 2])
s = Scaled([3])
print(a + [4], a * 2, 2 * a)
print(s * 2, 2 * s, s + [4])


class Pair(list[int]):
    def __add__(self, other: Scaled) -> list[int]:
        return [self[0], other[0]]


print(Pair([7]) + s)
