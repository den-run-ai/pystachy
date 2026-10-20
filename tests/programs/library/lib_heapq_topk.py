# lib/heapq.py's nsmallest() and nlargest() (CPython's Lib/heapq.py with the marked edits that
# lib/README.md lists), against CPython's own: with and without key=, ties, n below 1, at and past
# the length, empty input, the iterables the subset can pass, and objects whose __lt__, __eq__,
# __iter__ and __len__ log their calls, so that the comparisons are CPython's, in its order
import heapq
from heapq import nlargest, nsmallest
from typing import Iterator

data = [5, 1, 8, 3, 9, 2, 7, 3, 8]
for n in [-1, 0, 1, 2, 3, 8, 9, 10, 100]:
    print(n, nsmallest(n, data), nlargest(n, data))
    print(n, nsmallest(n, data, key=lambda x: -x), nlargest(n, data, key=lambda x: x % 4))
empty: list[int] = []
for n in [-1, 0, 1, 2]:
    print(n, nsmallest(n, empty), nlargest(n, empty), nsmallest(n, empty, key=abs), nlargest(n, empty, key=abs))
print(nsmallest(3, [2.5, -1.0, 3.25, 0.0, -7.5]), nlargest(2, [2.5, -1.0, 3.25, 0.0, -7.5], key=abs))
words = ["pear", "Fig", "apple", "kiwi", "Banana", "date", "cherry"]
print(nsmallest(3, words), nlargest(3, words), nsmallest(3, words, key=str.lower), nlargest(2, words, key=len))

# ties keep the input's order: the (elem, order) and (key, order, elem) tuples
scores = [("ann", 3), ("bob", 5), ("cy", 3), ("dee", 5), ("eve", 1), ("fay", 5), ("gus", 3)]
for n in [2, 3, 4, 6, 7]:
    print(n, nlargest(n, scores, key=lambda p: p[1]), nsmallest(n, scores, key=lambda p: p[1]))
pairs = [(1, "z"), (0, "b"), (1, "a"), (0, "a"), (2, "c")]
print(nsmallest(3, pairs), nlargest(3, pairs), nsmallest(1, pairs, key=lambda p: p[1]))


log: list[str] = []


class Lt:
    # ordered by its value alone; == is identity, as object's
    def __init__(self, v: int, tag: str) -> None:
        self.v = v
        self.tag = tag

    def __lt__(self, other: "Lt") -> bool:
        log.append(f"{self.tag}<{other.tag}")
        return self.v < other.v

    def __repr__(self) -> str:
        return self.tag


class LtEq:
    # also an __eq__, which comparing the (elem, order) tuples calls first
    def __init__(self, v: int, tag: str) -> None:
        self.v = v
        self.tag = tag

    def __lt__(self, other: "LtEq") -> bool:
        log.append(f"{self.tag}<{other.tag}")
        return self.v < other.v

    def __eq__(self, other: "LtEq") -> bool:
        log.append(f"{self.tag}={other.tag}")
        return self.v == other.v

    def __repr__(self) -> str:
        return self.tag


vals = [4, 1, 4, 7, 1, 9, 4, 0, 7, 2]
lts = [Lt(v, f"{'abcdefghij'[i]}{v}") for i, v in enumerate(vals)]
for n in [1, 2, 3, 5, 10, 11]:
    log.clear()
    r = nsmallest(n, lts)
    print("nsmallest", n, r, len(log), " ".join(log))
    log.clear()
    r = nlargest(n, lts)
    print("nlargest", n, r, len(log), " ".join(log))
eqs = [LtEq(v, f"{'abcdefghij'[i]}{v}") for i, v in enumerate(vals)]
eqs.append(eqs[3])  # (the same object twice: CPython's == of an object and itself calls no __eq__)
for n in [2, 4]:
    log.clear()
    e = nsmallest(n, eqs)
    print("nsmallest", n, e, len(log), " ".join(log))
    log.clear()
    e = nlargest(n, eqs)
    print("nlargest", n, e, len(log), " ".join(log))


def lt_key(p: tuple[str, int]) -> Lt:
    log.append(f"key({p[0]})")
    return Lt(p[1], p[0])


for n in [1, 3, 7, 8]:
    log.clear()
    r2 = nsmallest(n, scores, key=lt_key)
    print("nsmallest key", n, r2, " ".join(log))
    log.clear()
    r2 = nlargest(n, scores, key=lt_key)
    print("nlargest key", n, r2, " ".join(log))


class Bag:
    # an iterable with a length: len() decides whether sorted() does the work
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        log.append("iter")
        return iter(self.xs)

    def __len__(self) -> int:
        log.append("len")
        return len(self.xs)


class Stream:
    # without a length: the heap does the work, whatever n is
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        log.append("iter")
        return iter(self.xs)


class Unsized:
    # a __len__ that raises TypeError: no length either
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)

    def __len__(self) -> int:
        raise TypeError("no length")


for n in [1, 2, 4, 6]:
    log.clear()
    print(n, nsmallest(n, Bag([5, 3, 8, 1])), nlargest(n, Bag([5, 3, 8, 1]), key=lambda x: -x), log)
    log.clear()
    print(n, nsmallest(n, Stream([5, 3, 8, 1])), nlargest(n, Stream([5, 3, 8, 1])), log)
    print(n, nsmallest(n, Unsized([5, 3, 8, 1])), nlargest(n, Unsized([5, 3, 8, 1]), key=lambda x: x % 3))
log.clear()
print(nsmallest(9, Stream([])), nlargest(9, Bag([])), log)


class Noisy:
    # a Stream of Lt objects: no length, so 5 >= 4 items still runs the heap
    def __init__(self, xs: list[Lt]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[Lt]:
        return iter(self.xs)


log.clear()
print(nsmallest(5, Noisy(lts[:4])), " ".join(log))
log.clear()
print(nsmallest(5, lts[:4]), " ".join(log))

t = (4, 9, 1, 7, 1)
print(nsmallest(2, t), nlargest(2, t), nsmallest(1, t), nlargest(3, t, key=lambda x: -x))
print(nsmallest(2, "heapq"), nlargest(3, "heapq"), nlargest(1, "heapq"))
counts = {"to": 4, "be": 4, "or": 2, "not": 1, "that": 3, "is": 2}
print(nsmallest(2, counts), nlargest(3, counts, key=counts.get), nlargest(3, counts, key=lambda w: counts[w]))
print(nlargest(4, counts.items(), key=lambda kv: kv[1]), nsmallest(2, counts.values()))
print(nsmallest(3, {50, 3, 8, 1, 21}), nlargest(2, frozenset([3, 8, 1])))

# a larger input, from a linear congruential generator: CPython's comparisons, counted
seed = 12345


def rand() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed >> 16


big = [Lt(rand() % 500, str(i)) for i in range(600)]
for n in [2, 10, 50, 599]:
    log.clear()
    s = nsmallest(n, big)
    print(n, [x.tag for x in s[:5]], len(log), log[-3:])
    log.clear()
    s = nlargest(n, big, key=lambda x: Lt(x.v // 3, x.tag))
    print(n, [x.tag for x in s[:5]], len(log), log[-3:])
nums = [rand() for _ in range(2000)]
print(nsmallest(5, nums) == sorted(nums)[:5], nlargest(7, nums) == sorted(nums, reverse=True)[:7])
print(nlargest(5, nums, key=lambda x: x % 1000), nsmallest(5, nums, key=lambda x: (x % 10, -x)))
print(heapq.nsmallest(3, nums)[0] == min(nums), heapq.nlargest(1, nums) == [max(nums)])


# a key that changes the list it is reading: each item is read once, before its key is called, as
# CPython's iterator reads it
mut = [5, 4, 3, 2, 1, 0]


def mutating_key(x: int) -> int:
    if mut[0] == 5:
        mut[0] = 0
    return x


print(nlargest(2, mut, key=mutating_key), mut)
mut[0] = 5
print(nsmallest(2, mut, key=mutating_key), mut)
mut[0] = 5
print(nlargest(3, mut, key=lambda x: -x), nsmallest(3, mut, key=mutating_key), mut)
