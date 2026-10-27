# pystachy: python-int
# The int that an object's __len__ or __hash__ returns, annotated or not, is a promoting int in a
# module that opts in, and len(), truth and hash() take it as CPython does: a negative length is a
# ValueError (past 64 bits too), one past 64 bits an OverflowError, and a hash past 64 bits is the
# hash of that int, which dicts and sets then use


class Sized:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self) -> int:
        return self.n


class Bag:
    # (no annotations: the result is the promoting int self.n holds)
    def __init__(self, n):
        self.n = n

    def __len__(self):
        return self.n


class Key:
    def __init__(self, n: int) -> None:
        self.n = n

    def __hash__(self) -> int:
        return self.n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Key) and other.n == self.n


class Doubled(Key):
    def __hash__(self) -> int:
        return self.n * 2


class Items:
    def __init__(self) -> None:
        self.xs = [1, 2, 3]

    def __len__(self) -> int:
        return len(self.xs) * 2 ** 64 // 2 ** 64

    def __iter__(self):
        return iter(self.xs)


def length(x) -> str:
    try:
        return str(len(x))
    except (ValueError, OverflowError) as e:
        return f"{type(e).__name__}: {e}"


def truth(x) -> str:
    try:
        return "true" if x else "false"
    except (ValueError, OverflowError) as e:
        return f"{type(e).__name__}: {e}"


for n in (0, 3, 2 ** 63 - 1, 2 ** 63, 2 ** 64, -1, -2 ** 63, -2 ** 64):
    print(n, length(Sized(n)), truth(Sized(n)), length(Bag(n)), truth(Bag(n)))
for n in (2 ** 61 - 1, 2 ** 61, 2 ** 63 - 1, 2 ** 63, 2 ** 64 + 7, -1, -2, -2 ** 63, -2 ** 63 - 1, -2 ** 64):
    print(n, hash(Key(n)), hash(Doubled(n)))
d = {Key(2 ** 64): "big", Key(5): "small", Doubled(2 ** 70): "doubled"}
print(d[Key(2 ** 64)], d[Key(5)], d[Doubled(2 ** 70)], Key(2 ** 64) in d, Key(2 ** 65) in d)
s = {Key(2 ** 70), Key(2 ** 70), Key(-1), Key(-2)}
print(len(s), Key(2 ** 70) in s)
if Sized(2 ** 64 - 2 ** 64 + 2):
    print("sized", len(Items()), list(Items()), sorted(Items()))
