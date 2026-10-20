# zip() makes the iterator of each operand in turn, and a dict's or a set's iterator records the
# size then: a later operand's __iter__ that changes it makes the traversal raise RuntimeError, and
# code that runs between making the iterators and traversing them (sum()'s start, sorted()'s
# reverse=) sees them made already (#92)
from typing import Iterator

d = {1: 10}


class Items:
    def __iter__(self) -> Iterator[int]:
        d[2] = 20
        return iter([7, 8])


# the issue: a later operand's __iter__ grows the dict
try:
    for k, v in zip(d, Items()):
        print(k, v)
except RuntimeError as e:
    print("caught", str(e))


def restore() -> int:
    del d[2]
    return 100


# the size the dict's iterator took is the dict's again when the traversal starts: no error
d = {1: 10}
print(sum((k * 10 + v for k, v in zip(d, Items())), restore()))


def rev() -> bool:
    del d[2]
    return True


d = {1: 10}
print(sorted(zip(d, Items()), reverse=rev()))

# sets: the same
s = {1}


class Grows:
    def __iter__(self) -> Iterator[int]:
        s.add(2)
        return iter([7, 8])


try:
    for k, v in zip(s, Grows()):
        print(k, v)
except RuntimeError as e:
    print("caught", str(e))


def shrink() -> int:
    s.discard(2)
    return 0


s = {1}
print(sum((k + v for k, v in zip(s, Grows())), shrink()))


# a change while the arguments are evaluated comes before any iterator is made: no error
def grow_d() -> list[int]:
    d[3] = 30
    return [5, 6, 7]


d = {1: 10, 2: 20}
print(list(zip(d, grow_d())))


def grow_s() -> list[int]:
    s.add(9)
    return [5, 6]


s = {1}
print(list(zip(s, grow_s())))

# the iterators are made in order: only those made before the change see it
d = {1: 10}
s = {5}


class Both:
    def __iter__(self) -> Iterator[int]:
        d[2] = 20
        return iter([0, 0])


try:
    print(list(zip(s, d, Both())))
except RuntimeError as e:
    print("caught", str(e))
d = {1: 10}
try:
    print(list(zip(s, Both(), d)))
except RuntimeError as e:
    print("caught", str(e))

# map() of several iterables zips them
d = {1: 10}
try:
    print(list(map(lambda k, v: k + v, d, Items())))
except RuntimeError as e:
    print("caught", str(e))

# dict views and unchanged containers
d = {1: 10, 2: 20}
print(list(zip(d.items(), [0, 1])), list(zip(d, d.values())))
print([k for k, _ in zip(d, "ab")], list(zip(s, [0])))

# a comprehension over zip(), as a for loop
d = {1: 10}
try:
    print([k + v for k, v in zip(d, Items())])
except RuntimeError as e:
    print("caught", str(e))
