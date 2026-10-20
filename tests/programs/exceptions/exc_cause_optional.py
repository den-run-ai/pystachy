# raise ... from err of an exception that may be None: the exception is the cause, None is none
# (as from None)


def from_exc(err: BaseException | None) -> None:
    try:
        raise ValueError("w") from err
    except ValueError as e:
        print(repr(e), repr(e.__cause__))


from_exc(None)
from_exc(KeyError("k"))
try:
    raise OSError("o")
except OSError as caught:
    from_exc(caught)
