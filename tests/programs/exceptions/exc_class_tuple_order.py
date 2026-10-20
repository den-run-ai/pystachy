# isinstance() and issubclass() test a tuple's classes in turn, as CPython does: the first that
# matches stops, so a None after it is never reached, and a None reached raises TypeError (for
# issubclass(), after its first argument is found to be no class)


def inst(e: BaseException | None, first: type[BaseException], c: type[BaseException] | None) -> str:
    try:
        return str(isinstance(e, (first, c)))
    except TypeError as x:
        return f"TypeError: {x}"


def sub(k: type[BaseException] | None, first: type[BaseException], c: type[BaseException] | None) -> str:
    try:
        return str(issubclass(k, (first, c)))
    except TypeError as x:
        return f"TypeError: {x}"


def nested(e: BaseException, t: tuple[type[BaseException], type[BaseException]] | None) -> str:
    try:
        return str(isinstance(e, (LookupError, t)))
    except TypeError as x:
        return f"TypeError: {x}"


def other(s: str, c: type[BaseException] | None) -> str:
    try:
        return str(isinstance(s, (KeyError, c)))
    except TypeError as x:
        return f"TypeError: {x}"


print(inst(ValueError("x"), Exception, None))
print(inst(ValueError("x"), KeyError, None))
print(inst(ValueError("x"), KeyError, ValueError))
print(inst(None, KeyError, None))
print(inst(None, KeyError, ValueError))
print(sub(ValueError, Exception, None))
print(sub(ValueError, KeyError, None))
print(sub(ValueError, KeyError, LookupError))
print(sub(None, KeyError, None))
print(sub(None, KeyError, ValueError))
print(nested(KeyError("k"), None))
print(nested(ValueError("v"), None))
print(nested(ValueError("v"), (KeyError, ValueError)))
print(nested(ValueError("v"), (KeyError, IndexError)))
print(other("s", None), other("s", ValueError))
