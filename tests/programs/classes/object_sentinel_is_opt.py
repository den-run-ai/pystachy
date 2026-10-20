# object()'s object compared with is and is not to a number or bool that may be None, where the
# sentinel may be None too: the same object only where both are None
_MISSING = object()


class Box:
    pass


def nulls(flag: bool, n: int | None, x: float | None, b: bool | None) -> None:
    s = _MISSING
    if not flag:
        s = None
    print(n is s, s is n, n is not s, s is not n)
    print(x is s, s is not x, b is s, s is not b)


def sentinel(n: int | None) -> None:
    print(n is _MISSING, n is not _MISSING, _MISSING is n, _MISSING is not n)


def objects(n: int | None, o: Box | None) -> None:
    print(n is o, o is n, n is not o)


nulls(False, None, None, None)
nulls(True, None, None, None)
nulls(False, 3, 2.5, True)
nulls(True, 3, 2.5, False)
sentinel(None)
sentinel(7)
objects(None, None)
objects(None, Box())
objects(4, None)
objects(4, Box())
