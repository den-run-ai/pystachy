# error: exc_class_call_kw.py:11: error: a call of an exception class held as a value is supported with positional arguments only
# CPython passes the keyword argument on to E.__init__; a class object takes positional ones here


class E(Exception):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)


def make(c: type[E]) -> E:
    return c(text="x")


print(repr(make(E)))
