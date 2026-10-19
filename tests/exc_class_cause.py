# raise ... from c of a class object that may be None: None is no cause (as from None), a class
# makes an object of it


class E(Exception):
    pass


def from_class(c: type[BaseException] | None) -> None:
    try:
        raise ValueError("v") from c
    except ValueError as e:
        print(repr(e), repr(e.__cause__))


from_class(None)
from_class(KeyError)
from_class(E)
