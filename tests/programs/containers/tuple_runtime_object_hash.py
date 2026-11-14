# hash() of a tuple of objects hashes each item as CPython's tuplehash does: through the class's
# __hash__, by identity where the class defines neither __eq__ nor __hash__, and TypeError where
# it defines __eq__ alone
class K:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: object) -> bool:
        return isinstance(other, K) and other.x == self.x

    def __hash__(self) -> int:
        print("hash", self.x)
        return self.x


class Plain:
    pass


class Unhashable:
    def __eq__(self, other: object) -> bool:
        return True


def ks(xs: list[int]) -> tuple[K, ...]:
    return tuple(K(x) for x in xs)


print(hash(ks([1, 2, 3])) == hash((1, 2, 3)))
print(hash(ks([])) == hash(()))
print(hash(ks([5, -1])))
p = Plain()
plain: tuple[Plain, ...] = (p, Plain())
again: tuple[Plain, ...] = (p, plain[1])
print(hash(plain) == hash(again))
bad: tuple[Unhashable, ...] = (Unhashable(),)
try:
    print(hash(bad))
except TypeError as e:
    print("TypeError:", e)
