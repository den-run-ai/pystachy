# "format" % x of a value of object takes what x holds as CPython does when it runs: a tuple's
# items as the arguments, a dict as the mapping of a format that names keys or has no
# conversion, a list or bytes as such a mapping too, and any other value as the one argument
def fmt(f: int, v: object) -> str:
    x: object = v
    try:
        if f == 0:
            return "%s" % x
        if f == 1:
            return "%s and %r" % x
        if f == 2:
            return "%(a)s/%(b)d" % x
        if f == 3:
            return "plain" % x
        return "%d%%" % x
    except (TypeError, KeyError, ValueError) as e:
        return f"{type(e).__name__}: {e}"


def main() -> None:
    values: list[object] = [(1,), (1, 2), (), ("a", "b"), {"a": 1, "b": 2}, {"a": "x"}, 5, "s", [1, 2], None, (3.7,)]
    for v in values:
        print([fmt(f, v) for f in range(5)])


main()
