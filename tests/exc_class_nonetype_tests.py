# NoneType's class object, which type() gives of an exception that is None: None is its instance
# (also where a tuple or a variable that may be None holds it), and it derives from no exception
# class, BaseException included


class E(Exception):
    pass


def kinds(e: BaseException | None) -> None:
    t = type(e)
    print(t.__name__, isinstance(e, t), isinstance(None, t), isinstance(KeyError("k"), t), isinstance("s", t))
    print(issubclass(t, BaseException), issubclass(t, Exception), issubclass(t, (KeyError, BaseException)), issubclass(t, t))
    b: type[BaseException] = BaseException
    print(issubclass(t, b), issubclass(KeyError, t), isinstance(e, (ValueError, t)), isinstance(None, (t, ValueError)))
    s: str | None = None
    print(isinstance(s, t))


def order(e: BaseException | None, c: type[Exception] | None) -> None:
    t = type(e)
    try:
        print(isinstance(None, (t, c)))
    except TypeError as x:
        print("TypeError", x)
    try:
        print(isinstance(None, (c, t)))
    except TypeError as x:
        print("TypeError", x)


def obj(x: E | None, e: E | None) -> None:
    t = type(e)
    print(isinstance(x, t), isinstance(x, (KeyError, t)))


kinds(None)
kinds(KeyError("k"))
order(None, None)
order(KeyError("k"), None)
obj(None, None)
obj(E("x"), None)
obj(None, E("y"))
obj(E("x"), E("y"))
