# class C(list) and class C(list[T]): an object is a list to every operation the class does not
# define, and stays an object of its class wherever a variable, a parameter, a field or a
# container of that class holds it.


class Stack(list):
    def top(self) -> int:
        return self[-1]

    def push(self, x: int) -> None:
        self.append(x)

    def total(self) -> int:
        t = 0
        for x in self:
            t += x
        return t


class Names(list[str]):
    sep = ", "

    def joined(self) -> str:
        return self.sep.join(self)

    def longest(self) -> str:
        return max(self, key=len)


class Matrix(list[list[float]]):
    def row_sums(self) -> list[float]:
        return [sum(r) for r in self]


class Registry:
    def __init__(self) -> None:
        self.stack = Stack()
        self.names: Names = Names()
        self.history: list[Stack] = []

    def record(self, x: int, name: str) -> None:
        self.stack.push(x)
        self.names.append(name)
        snapshot = Stack(self.stack)
        self.history.append(snapshot)


def drain(s):
    out = []
    while s:
        out.append(s.pop())
    return out


def largest(s: Stack) -> int:
    return max(s)


def build(n: int) -> Stack:
    s = Stack()
    for i in range(n):
        s.push(i * i)
    return s


s = Stack()
print(len(s), bool(s), s == [], s)
s.push(3)
s.append(4)
s.extend([5, 6])
s.insert(0, 1)
s += [7]
print(s, s.top(), s.total(), len(s), bool(s))
print(s[0], s[-2], s[1:3], s[::-1], type(s[1:3]).__name__, type(s + [8]).__name__, type(s * 2).__name__)
print(s + [8], [0] + s, s * 2, s.copy(), type(s.copy()).__name__)
print(sorted(s, reverse=True), sum(s), max(s), min(s), list(s), tuple(s), set(s) == {1, 3, 4, 5, 6, 7})
print([x * 2 for x in s], [i for i, x in enumerate(s) if x % 2], list(zip(s, "abc")), list(reversed(s)))
print(3 in s, 9 in s, 9 not in s, s.index(4), s.count(5), any(x > 6 for x in s), all(s))
s[0] = 10
s[1:3] = [30, 40, 50]
del s[-1]
del s[0:1]
print(s, repr(s), str(s), f"{s}", "{}".format(s), "%s" % s)
s.sort(reverse=True)
s.reverse()
s.remove(40)
print(s, s == [5, 6, 30, 50], s != [5, 6, 30, 50], s < [5, 7], s >= [5, 6, 30, 50], [5, 6, 30, 50] == s)
t = Stack([5, 6, 30, 50])
print(s == t, s is t, t is t, s != t, s is not t)
print(isinstance(s, list), isinstance(s, Stack), isinstance(s, Names), type(s).__name__, type(s) is Stack, type(s) is list)
a, b, c, d = s
first, *rest = s
print(a, b, c, d, first, rest, [*s, 0], (*s,))
print(largest(s), drain(t), len(t), build(5), build(4).top(), drain(build(3)))

names = Names(["ada", "grace", "barbara"])
names.append("mary")
print(names, names.joined(), names.longest(), len(names), names[1].upper(), sorted(names))
print(isinstance(names, list), isinstance(names, Stack), type(names).__name__, Names.sep, names.sep)
m = Matrix()
m.append([1.0, 2.5])
m.append([4.0])
print(m, m.row_sums(), m[0][1], len(m[1]))

r = Registry()
for i, n in enumerate(["x", "y", "z"]):
    r.record(i + 1, n)
print(r.stack, r.names.joined(), r.history, [h.top() for h in r.history], r.history[1] == [1, 2])
by_name: dict[str, Stack] = {"sq": build(3), "empty": Stack()}
print(by_name, by_name["sq"].total(), sorted(by_name), [len(v) for v in by_name.values()])
pair = (build(2), Names(["p"]))
print(pair, pair[0].top(), pair[1].joined())
none: Stack | None = None
print(none, none is None, none == s)
none = s
print(none.top() if none is not None else -1)
