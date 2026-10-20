# type(x) of an exception x that is None is NoneType's class object: it is type(None), its module
# is builtins, and raise of it raises CPython's TypeError. type(e).__module__ is its class's module


class E(Exception):
    pass


def check(x: E | None) -> None:
    print(type(x) is type(None), type(x) == type(None), type(x) is not type(None), type(x) != type(None))
    t = type(x)
    print(t is type(None), type(None) is t, t.__name__, t.__module__, type(x).__module__)


def raised(x: E | None) -> None:
    t = type(x)
    try:
        raise t
    except TypeError as err:
        print("TypeError:", err)
    except E as err:
        print("E", repr(err))
    try:
        raise ValueError("v") from t
    except TypeError as err:
        print("TypeError:", err)
    except ValueError as err:
        print("ValueError", err, repr(err.__cause__))


def module(e: E) -> str:
    return type(e).__module__


def omodule(e: BaseException | None) -> str:
    return type(e).__module__


check(None)
check(E("e"))
raised(None)
raised(E("e"))
print(module(E("x")), omodule(None), omodule(KeyError("k")))
try:
    raise E("y")
except Exception as e:
    print(type(e).__module__, type(e).__qualname__)
counts: dict[str, int] = {}
try:
    print(counts["k"])
except Exception as e:
    print(type(e).__module__, type(e).__name__)
