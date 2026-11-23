# == and != of Protocol values whose implementations Pystachy once could not compare with each
# other: a class without __eq__ on the left of one whose __eq__ never returns NotImplemented
# (reflected, as CPython calls it), two classes without one (identity), and a builtin value
# beside an object. No pair of implementations rejects the comparison.
from typing import Protocol


class Sized(Protocol):
    def __len__(self) -> int: ...


class Plain:
    def __len__(self) -> int:
        return 1


class Other:
    def __len__(self) -> int:
        return 1


class Counted:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self) -> int:
        return self.n

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Counted):
            print("Counted.__eq__(Counted)")
            return other.n == self.n
        if isinstance(other, list):
            print("Counted.__eq__(list)")
            return len(other) == self.n
        if isinstance(other, str):
            print("Counted.__eq__(str)")
            return len(other) == self.n
        print("Counted.__eq__(other)")
        return False


def same(a: Sized, b: Sized) -> bool:
    return a == b


def differ(a: Sized, b: Sized) -> bool:
    return a != b


def main() -> None:
    plain = Plain()
    xs: list[Sized] = [plain, Other(), Counted(2), Counted(2), [7, 8], "ab", [7, 8], "ab", "abc"]
    names = ["plain", "other", "counted", "counted'", "list", "str", "list'", "str'", "abc"]
    for i in range(len(xs)):
        row: list[str] = []
        for j in range(len(xs)):
            eq = same(xs[i], xs[j])
            ne = differ(xs[i], xs[j])
            row.append(("=" if eq else ".") + ("!" if ne else "."))
        print(names[i], " ".join(row))
    # a protocol value beside a value of a class and of a builtin type
    s: Sized = Counted(3)
    p: Sized = plain
    print(s == plain, plain == s, p == plain, plain == p, p == Other(), Other() == p)
    print(s == [1, 2, 3], [1, 2, 3] == s, p == [1], [1] == p, s == "abc", "abc" == s, p == "a", "a" == p)
    print(s != plain, plain != s, p != plain, plain != p, s != [1, 2, 3], [1, 2, 3] != s)


main()
