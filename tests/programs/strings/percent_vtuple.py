# "fmt" % t of a tuple of any length (tuple[T, ...]): its items are the arguments, as many as it
# has, and too few or too many raise CPython's TypeError when the formatting runs; a tuple that may
# be None is one argument where it is None
def fmt(args: tuple[int, ...]) -> str:
    try:
        return "%s+%d" % args
    except TypeError as e:
        return "TypeError: " + str(e)


def one(args: tuple[str, ...]) -> str:
    try:
        return "<%s>" % args
    except TypeError as e:
        return "TypeError: " + str(e)


def none(args: tuple[str, ...]) -> str:
    try:
        return "plain" % args
    except TypeError as e:
        return "TypeError: " + str(e)


def maybe(args: tuple[int, ...] | None) -> str:
    try:
        return "%s %s" % args
    except TypeError as e:
        return "TypeError: " + str(e)


def main() -> None:
    print(fmt((1, 2)))
    print(fmt((1,)))
    print(fmt((1, 2, 3)))
    print(fmt(()))
    print(one(("a",)))
    print(one(("a", "b")))
    print(one(()))
    print(none(()))
    print(none(("x",)))
    print(maybe((1, 2)))
    print(maybe(None))
    print(maybe((1,)))
    xs: list[int] = [4, 5]
    print("%d-%d" % tuple(xs))
    print("%5.1f|%-4d|%r" % tuple([1.25, 2.0, 3.5]))


main()
