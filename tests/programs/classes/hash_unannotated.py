# An unannotated __hash__ infers its result, int or bool, as an unannotated __len__ does: sets,
# dict keys and hash() call it, a subclass's own __hash__ too.
class P:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __eq__(self, other: object) -> bool:
        return isinstance(other, P) and self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))


class Q(P):
    def __hash__(self):
        return self.x * 31 + self.y


class Flag:
    def __hash__(self):
        return True


s = {P(1, 2), P(1, 2), P(2, 1)}
print(len(s), P(1, 2) in s, P(3, 4) in s, hash(P(3, 4)) == hash((3, 4)))
d = {P(1, 2): "a"}
d[P(1, 2)] = "b"
print(d[P(1, 2)], len(d), hash(Q(1, 2)), len({Q(1, 2), Q(1, 2)}), Q(1, 2).__hash__())
print(hash(Flag()), Flag().__hash__())
