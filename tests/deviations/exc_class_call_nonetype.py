# type(x) of an exception x that is None is NoneType's class object, which Pystachy keeps as an
# exception class's: a call of it raises TypeError, where CPython returns None. A call of an
# exception's class makes an object of it, as in CPython (tests/exc_class_nonetype.py: the rest)


class E(Exception):
    pass


def call(x: E | None) -> None:
    t = type(x)
    try:
        print(repr(t()))
    except TypeError as err:
        print("TypeError:", err)


call(None)
call(E("e"))
