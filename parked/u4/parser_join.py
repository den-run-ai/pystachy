from typing import Callable

class Result:
    def __init__(self, status: bool, index: int, value, furthest: int, expected: frozenset[str]):
        self.status = status
        self.index = index
        self.value = value
        self.furthest = furthest
        self.expected = expected

    @staticmethod
    def success(index, value):
        return Result(True, index, value, -1, frozenset())

    @staticmethod
    def failure(index, expected):
        return Result(False, -1, None, index, frozenset([expected]))

    def aggregate(self, other):
        if other is None:
            return self
        if self.furthest > other.furthest:
            return self
        if self.furthest == other.furthest:
            return Result(self.status, self.index, self.value, self.furthest, self.expected | other.expected)
        return Result(self.status, self.index, self.value, other.furthest, other.expected)

    def __repr__(self) -> str:
        return f"Result({self.status}, {self.index}, {self.value!r}, {self.furthest}, {sorted(self.expected)})"


class Parser:
    def __init__(self, fn: Callable[[str, int], Result], name: str):
        self.fn = fn
        self.name = name

    def __call__(self, s: str, i: int):
        return self.fn(s, i)

    def alt(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            if r.status:
                return r
            return other(s, i).aggregate(r)

        return Parser(run, self.name + " | " + other.name)

    def then(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            if not r.status:
                return r
            return other(s, r.index).aggregate(r)

        return Parser(run, self.name + " " + other.name)

    def parse(self, s: str):
        r = self(s, 0)
        if r.status and r.index == len(s):
            return r.value
        raise ValueError(f"expected one of {sorted(r.expected)} at {r.furthest}")


def char(c: str) -> Parser:
    def run(s: str, i: int):
        if i < len(s) and s[i] == c:
            return Result.success(i + 1, c)
        return Result.failure(i, repr(c))

    return Parser(run, repr(c))


def digit() -> Parser:
    def run(s: str, i: int):
        if i < len(s) and s[i].isdigit():
            return Result.success(i + 1, int(s[i]))
        return Result.failure(i, "a digit")

    return Parser(run, "digit")


def main() -> None:
    d = digit()
    a = char("a")
    either = d.alt(a)
    print(d.parse("7"), a.parse("a"), either.parse("3"), either.parse("a"), either.name)
    for s in ["x", "", "77"]:
        try:
            print(either.parse(s))
        except ValueError as e:
            print("ValueError:", e)
    pair = a.then(d)
    print(pair.parse("a5"), pair.name)
    try:
        pair.parse("ab")
    except ValueError as e:
        print("ValueError:", e)


main()
