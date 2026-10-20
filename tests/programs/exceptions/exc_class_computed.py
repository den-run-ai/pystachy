# isinstance() and issubclass() of class objects that an expression gives: type(e), an item, a
# call (evaluated once, as CPython evaluates its arguments), a field of a field and a conditional
# expression, alone and in tuples


class Missing(LookupError):
    pass


class Holder:
    def __init__(self, kind: type[Exception]) -> None:
        self.kind = kind


class Outer:
    def __init__(self, kind: type[Exception]) -> None:
        self.inner = Holder(kind)


def pick(c: type[Exception]) -> type[Exception]:
    print("pick", c.__name__)
    return c


def same(e: BaseException, x: BaseException) -> None:
    print(isinstance(x, type(e)), issubclass(type(x), type(e)), issubclass(type(e), type(x)))


def maybe(e: BaseException | None) -> None:
    print(isinstance(e, type(e)), issubclass(type(e), type(e)), isinstance(None, (ValueError, type(e))))


same(LookupError("l"), KeyError("k"))
same(KeyError("k"), KeyError("k2"))
maybe(None)
maybe(KeyError("k"))
m = Missing("m")
print(isinstance(m, type(m)), issubclass(type(m), LookupError), issubclass(LookupError, type(m)))
classes = [KeyError, ValueError, Missing]
kinds = {"lookup": LookupError, "value": ValueError}
o = Outer(LookupError)
for x in [KeyError("k"), ValueError("v"), IndexError("i")]:
    print(isinstance(x, classes[0]), isinstance(x, kinds["lookup"]), isinstance(x, o.inner.kind), isinstance(x, (classes[1], kinds["value"])))
print(isinstance(Missing("m"), pick(LookupError)), issubclass(Missing, pick(ValueError)))
print(isinstance(KeyError("k"), (pick(ValueError), pick(KeyError))), issubclass(Missing, (classes[1], LookupError)))
flag = len(classes) > 2
print(isinstance(ValueError("v"), ValueError if flag else KeyError), issubclass(Missing, classes[2] if flag else ValueError))
try:
    raise Missing("x")
except LookupError as e:
    print(isinstance(e, (type(e), ValueError)), issubclass(type(e), (ValueError, type(e))), isinstance(e, classes[2]))
