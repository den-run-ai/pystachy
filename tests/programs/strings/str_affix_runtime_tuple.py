# str.startswith() and str.endswith() of a tuple of str whose length the run decides
# (tuple[str, ...]): the items in order, True at the first that matches and False for no item,
# with the optional start and end; an item that is None raises when it is reached
def words(n: int) -> tuple[str, ...]:
    out: list[str] = []
    for i in range(n):
        out.append("w" + str(i))
    return tuple(out)


def none_or(n: int) -> tuple[str, ...] | None:
    return words(n) if n >= 0 else None


class Blocked:
    def __init__(self, ends: tuple[str, ...]) -> None:
        self.ends = ends

    def hit(self, s: str) -> bool:
        return s.startswith(self.ends) or s.endswith(self.ends)


def main() -> None:
    t = words(3)
    print("w2x".startswith(t), "xw2".startswith(t), "xw2".endswith(t), "xw9".endswith(t))
    print("abc".startswith(words(0)), "abc".endswith(words(0)), "".startswith(words(0)))
    # start and end, also negative and past the end
    print("aw1".startswith(t, 1), "aw1".startswith(t, 2), "w1a".endswith(t, 0, 2), "w1a".endswith(t, 0, 1))
    print("aw1b".startswith(t, -3), "aw1b".endswith(t, -3, -1), "w0".startswith(t, 5), "w0".endswith(t, None, 9))
    # a field, of a set's items (tuple() of a set) and of a slice
    b = Blocked(tuple(sorted({"ab", "cd"})))
    print(b.hit("abx"), b.hit("xcd"), b.hit("xyz"), "w1".startswith(t[1:]), "w0".startswith(t[1:]))
    one = tuple({"only"})
    print("only this".startswith(one), "not only".endswith(one), "neither".endswith(one))
    # the empty string matches everywhere; a longer item never matches a shorter string
    empty: tuple[str, ...] = tuple([""])
    print("abc".startswith(empty), "".endswith(empty), "w".startswith(t))
    # None among the items raises where it is reached, and not after a match
    maybe: tuple[str | None, ...] = tuple(["zz", None, "ab"])
    print("zzz".startswith(maybe))
    for s in ["abc", ""]:
        try:
            print(s.endswith(maybe))
        except TypeError as error:
            print("TypeError", error)
    try:
        print("abc".startswith(none_or(-1)))  # type: ignore[arg-type]
    except TypeError as error:
        print("TypeError", error)
    # the tuple is evaluated once, before the bounds
    calls: list[str] = []

    def noted(tag: str, items: tuple[str, ...]) -> tuple[str, ...]:
        calls.append(tag)
        return items

    def bound(tag: str, i: int) -> int:
        calls.append(tag)
        return i

    print("zw1".startswith(noted("tuple", t), bound("start", 1), bound("end", 3)), calls)
    print([name for name in ["w0.txt", "x.txt", "w2"] if name.startswith(t)])


main()
