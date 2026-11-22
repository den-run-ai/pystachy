# Iterating objects of list subclasses: every builtin and statement that iterates takes list's
# items unless the class defines __iter__ (or __reversed__, for reversed()), which list's own
# reversed() ignores; min() and max() of two objects compare them and return one of them.
from typing import Iterator


class S(list[int]):
    pass


def gen(s: S):
    yield from s


s = S([3, 1, 2])
fk: dict[int, int | None] = dict.fromkeys(s)
print(list(reversed(s)), list(iter(s)), next(iter(s)), list(enumerate(s, 1)), list(zip(s, s)))
print(list(map(lambda x: x + 1, s)), list(filter(lambda x: x > 1, s)), sorted(s), min(s), max(s), sum(s))
print(any(s), all(s), tuple(s), set(s) == {1, 2, 3}, fk, " ".join([str(x) for x in s]))
print([*s], (*s, 9), list(gen(s)), [x for x in s if x != 1], {x: 1 for x in s})
for i, x in enumerate(list(reversed(s))):
    print(i, x, end=" ")
print()
a, *b = s
print(a, b, max(s, key=lambda x: -x), sorted(s, key=lambda x: -x), s.index(2), sum(s, 10))


class Own(list[int]):
    def __iter__(self) -> Iterator[int]:
        return iter([100, 200])


o = Own([3, 1, 2])
print(list(reversed(o)), len(o), o[0], list(o), [x for x in o], sorted(o))
for x in o:
    print(x, end=" ")
print()


class Tagged(list[int]):
    def tag(self) -> str:
        return "T" + str(len(self))


t1 = Tagged([1])
t2 = Tagged([2, 0])
m = max(t1, t2)
print(m, type(m).__name__, m.tag(), min(t1, t2).tag(), max([t1, t2]).tag(), sorted([t2, t1])[0].tag())


class Back(list[int]):
    def __reversed__(self) -> Iterator[int]:
        return iter([7, 7])


r = Back([1, 2])
print(list(reversed(r)), [x for x in reversed(r)], list(r))
