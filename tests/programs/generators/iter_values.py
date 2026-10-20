# Iterators as values: in fields (of a class whose __init__ calls iter(), or that takes an
# iterator), passed to and returned from functions, held in lists, read by closures and
# lambdas, module-level ones read in functions, and wrappers of other iterators, as an
# itertools-style class is; next(it, None) in a while loop; iter as a function value.
import builtins


class Tokens:
    def __init__(self, text: str) -> None:
        self.it = iter(text)
        self.n = 0

    def __iter__(self):
        return self

    def __next__(self) -> str:
        c = next(self.it)
        self.n += 1
        return c.upper()


class Firsts:
    def __init__(self, xs: list[int]) -> None:
        self.it = iter(xs)
        self.first = next(self.it, -1)


class Chain:
    def __init__(self, a, b):
        self.a = iter(a)
        self.b = iter(b)
        self.first = True

    def __iter__(self):
        return self

    def __next__(self):
        if self.first:
            x = next(self.a, None)
            if x is not None:
                return x
            self.first = False
        return next(self.b)


class Skip:
    def __init__(self, it, n: int) -> None:
        self.it = it
        self.n = n

    def __iter__(self):
        return self

    def __next__(self):
        while self.n > 0:
            next(self.it)
            self.n -= 1
        return next(self.it)


def head(it):
    return next(it, None)


def make(xs: list[int]):
    return iter(xs)


def drain(it) -> list[int]:
    out: list[int] = []
    while True:
        x = next(it, None)
        if x is None:
            break
        out.append(x)
    return out


g = iter([5, 6, 7])


def use_global() -> int:
    return next(g)


def outer() -> list[int]:
    it = iter(range(5))

    def take() -> int:
        return next(it)

    return [take(), take(), next(it)]


t = Tokens("abc")
print(list(t), t.n, next(t, "end"))
fs = Firsts([4, 5, 6])
print(fs.first, list(fs.it), Firsts([]).first)
m = make([1, 2, 3])
print(head(m), drain(m), head(m))
print(use_global(), list(g), next(g, 0))
its = [iter("ab"), iter("cd")]
print([next(i) for i in its], [list(i) for i in its])
f = lambda: next(iter([42]))
print(f(), outer())
none: list[int] = []
print(list(Chain([1, 2], [3])), list(Chain("ab", "cd")), list(Chain(none, [9])))
print(list(Skip(iter([1, 2, 3, 4]), 2)), list(Skip(Chain([1, 2], [3, 4]), 1)))
c = Chain([1], [2, 3])
for x in c:
    print("chain", x)
print(next(c, -1))
s = Skip(iter("xyz"), 1)
print(next(s), "".join(s))
pairs = iter([1, 2, 3, 4])
print(list(zip(pairs, pairs)))
ws = iter(["b", "a", "c"])
print(sorted(ws), sorted(ws))
print(set(iter([1, 2, 2])), min(iter([4, 2])), max(iter("az")))
print(list(map(lambda x: x * 3, iter([1, 2]))), list(enumerate(iter("xy"), 1)))
print(list(filter(lambda x: x > 1, iter([1, 2, 3]))), tuple(iter("ok")))
nested = iter([[1, 2], [3]])
print([len(x) for x in nested], list(nested))
its2 = list(map(iter, [[1, 2], [3]]))
mk = iter
print([next(i) for i in its2], next(mk("q")), next(builtins.iter([4])), list(its2[0]))
