# type(e) of an exception that may be None (BaseException | None) is a class object: NoneType's
# for None, else the exception's class, which a comparison, __name__, __module__ and a call read


def kind(e: BaseException | None) -> str:
    t = type(e)
    same = type(e) is KeyError
    none = type(e) is type(None)
    return f"{t.__name__} {t.__module__} {same} {none} {type(e) == type(e)}"


def again(e: BaseException | None) -> str:
    if e is None:
        return "none"
    return repr(type(e)("again"))


print(kind(None))
print(kind(KeyError("k")))
try:
    raise OSError("o")
except OSError as caught:
    print(kind(caught), again(caught))
print(again(None), again(ValueError("v")))
