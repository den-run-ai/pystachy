# a str method's start or end that is None (also an int | None or bool | None that is None) is
# omitted, as CPython takes it
def gi(flag: bool) -> int | None:
    return -2 if flag else None


def gb(flag: bool) -> bool | None:
    return True if flag else None


s = "abcabc"
n: int | None = None
print(s.find("b", None), s.count("c", 0, None), s.startswith("a", None), s.endswith("c", None, None), s.rfind("b", None, 3))
print(s.index("c", n), s.rindex("a", n, n), s.find("c", gi(True)), s.find("c", gi(False)), s.count("b", gb(True)), s.find("a", gb(False), gi(True)))
print(s.endswith("b", gi(False), gi(True)), s.startswith("c", gi(True)))


def main() -> None:
    x = gi(False)
    print("abc".find("b", x), "abc".startswith("b", x), "abc".index("c", x, x))


main()
