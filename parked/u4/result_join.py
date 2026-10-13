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


def digit(s, i):
    if i < len(s) and s[i].isdigit():
        return Result.success(i + 1, int(s[i]))
    return Result.failure(i, "a digit")


def letter(s, i):
    if i < len(s) and s[i].isalpha():
        return Result.success(i + 1, s[i])
    return Result.failure(i, "a letter")


def main() -> None:
    r1 = digit("7x", 0)
    r2 = digit("x", 0)
    print(r1, r2, r1.status, r2.status, r1.value, r2.value, r1.index, r2.furthest)
    print(r2.aggregate(r1), r1.aggregate(None), digit("x", 0).aggregate(letter("1", 0)))
    print([digit(s, 0) for s in ["1", "a", ""]], letter("q", 0).value)


main()
