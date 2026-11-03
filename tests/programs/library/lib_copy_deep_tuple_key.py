# deepcopy() of an object reads each attribute as the copy reaches it where copying an earlier one
# may run the program's code: here the __hash__() of a key's tuple item (also in a nested tuple of
# a set's items), which inserting the copied key into the copy runs, changes a later attribute of
# the original, which the copy gets
import copy


class Key:
    def __hash__(self) -> int:
        if TARGET:
            TARGET[0].later = 9
        return 7

    def __eq__(self, other: object) -> bool:
        return self is other


class Box:
    def __init__(self) -> None:
        self.table: dict[tuple[Key, int], int] = {(Key(), 1): 2}
        self.later = 1


class NKey:
    def __hash__(self) -> int:
        if NTARGET:
            NTARGET[0].later = 8
        return 5

    def __eq__(self, other: object) -> bool:
        return self is other


class Nested:
    def __init__(self) -> None:
        self.items: set[tuple[str, tuple[NKey, int]]] = {("k", (NKey(), 3))}
        self.later = 1


TARGET: list[Box] = []
b = Box()
TARGET.append(b)
c = copy.deepcopy(b)
print(b.later, c.later, len(c.table))
NTARGET: list[Nested] = []
n = Nested()
NTARGET.append(n)
m = copy.deepcopy(n)
print(n.later, m.later, len(m.items))
