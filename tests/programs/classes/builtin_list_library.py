# Objects of list subclasses handed to code that takes any list: the library's functions
# (specialized for the class, as for any argument's type), iterators, generators and sorting.
# A bare base takes its item type from the first fill, wherever the program makes it: a
# constructor's iterable, a method's append, an __init__ parameter without an annotation.
import bisect
import heapq
import random
from functools import reduce
from itertools import chain


class Stack(list[int]):
    def top(self) -> int:
        return self[-1]


class Tagged(list):
    def __init__(self, tag, items):
        super().__init__(items)
        self.tag = tag

    def describe(self) -> str:
        return "{}:{}".format(self.tag, len(self))


class Lines(list):
    def add(self, text: str) -> "Lines":
        self.append(text.strip())
        return self

    def width(self) -> int:
        return max([len(x) for x in self]) if self else 0


class Late(list):
    def first(self) -> float:
        return self[0]


def fill(v: Late) -> None:
    v.append(1.5)


def gen(v: Stack):
    yield from v
    yield len(v)


s = Stack([3, 1, 2])
print(list(map(str, s)), list(filter(None, s)), reduce(lambda a, b: a + b, s), list(chain(s, s)))
print(dict(enumerate(s)), {x: x * x for x in s}, {x for x in s if x > 1} == {2, 3})
it = iter(s)
print(next(it), next(it), list(it))
heapq.heapify(s)
print(s, heapq.heappop(s), s)
bisect.insort(s, 2)
print(s, bisect.bisect_left(s, 3))
random.seed(1)
random.shuffle(s)
print(sorted(s), random.choice(s) in s)
print(s.top(), hash(tuple(s)) == hash(tuple(list(s))), len(str(s)), ",".join(str(x) for x in s) != "")
x = s if len(s) > 1 else Stack()
print(type(x).__name__, x is s)
print(list(gen(Stack([1, 2]))))
print(len(s or Stack()), len(Stack() or s), not s, not Stack())
t = s
t.append(99)
print(s[-1], t is s)
u = [Stack([1]), Stack([0, 5]), Stack()]
u.sort()
print(u, sorted(u, key=len), max(u), Stack([0, 5]) in u, u.index(Stack([1])), u.count(Stack()))
print([len(q) for q in u], [q.top() for q in u if q])
try:
    print({Stack([1]): "one"})
except TypeError as e:
    print("TypeError:", e)

a = Tagged("a", ["x", "y"])
b = Tagged(7, ["z"])
print(a, b, a.describe(), b.describe(), a.tag, b.tag + 1, a + b, type(a).__name__)
lines = Lines().add("  one ").add("three  ")
print(lines, lines.width(), Lines().width(), " | ".join(lines))
late = Late()
print(len(late), bool(late))
fill(late)
print(late.first(), late)
