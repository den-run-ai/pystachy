# == and != between an object and a value of a builtin type, where the object's class has no
# subclass: a builtin value's own method declines an object, so CPython calls the reflected method
# of the object's class, and where it has none compares identity: never equal
class Plain:
    def __init__(self, n: int) -> None:
        self.n = n


class Size:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            print("Size.__eq__(list)")
            return len(other) == self.n
        if isinstance(other, dict):
            print("Size.__eq__(dict)")
            return len(other) == self.n
        if isinstance(other, tuple):
            print("Size.__eq__(tuple)")
            return len(other) == self.n
        if isinstance(other, bytes):
            print("Size.__eq__(bytes)")
            return len(other) == self.n
        if isinstance(other, set):
            print("Size.__eq__(set)")
            return len(other) == self.n
        print("Size.__eq__(other)")
        return False


def main() -> None:
    c = Plain(1)
    s = Size(2)
    xs = [1, 2]
    m = {"a": 1, "b": 2}
    t = (1, "a")
    by = b"ab"
    st = {1, 2}
    # no method: False and True, in both orders
    print(c == xs, xs == c, c != xs, xs != c)
    print(c == m, m == c, c != m, m != c)
    print(c == t, t == c, c != t, t != c)
    print(c == by, by == c, c != by, by != c)
    print(c == st, st == c, c != st, st != c)
    print(c == "s", "s" == c, c != "s", "s" != c)
    print(c == 1, 1 == c, c != 1, 1 != c)
    print(c == 1.5, 1.5 == c, c != 1.5, 1.5 != c)
    print(c == True, True == c, c != False, False != c)
    # the object's __eq__, also reflected with the value on the left
    print(s == xs, xs == s, s != xs, xs != s)
    print(s == m, m == s, s != m, m != s)
    print(s == t, t == s, s != t, t != s)
    print(s == by, by == s, s != by, by != s)
    print(s == st, st == s, s != st, st != s)
    print(s == [1], [1] == s)
    print(s == "s", "s" == s, s == 2, 2 == s)


main()
