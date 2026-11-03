# deepcopy() of a set copies a list of its items, as CPython's __reduce__ of a set gives them, then
# makes the new set: a __deepcopy__() of an item that empties the original set changes neither the
# items copied nor the copy (CPython raises no "Set changed size during iteration")
import copy


class E:
    def __init__(self, n: int) -> None:
        self.n = n

    def __hash__(self) -> int:
        return self.n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, E) and other.n == self.n

    def __deepcopy__(self, memo) -> "E":
        S.clear()
        return E(self.n * 10)


S: set[E] = {E(1), E(2)}
c = copy.deepcopy(S)
print(len(S), sorted([e.n for e in c]))
