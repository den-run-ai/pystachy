# Calls of exception classes held as values: type(e)(...) remakes an exception of e's class,
# also of a class of the program that no code names as a value; a class whose __init__ takes
# other arguments raises CPython's TypeError; a with statement's __exit__ compares the class it
# gets; contextlib.suppress() kept as a value


class Quiet(Exception):
    pass


class Pair(Exception):
    def __init__(self, a: str, b: str) -> None:
        super().__init__(a + b)


def again(e: Exception, text: str) -> Exception:
    return type(e)(text)


def fail(k: int) -> None:
    if k == 0:
        raise Quiet("q")
    if k == 1:
        raise KeyError("k")
    raise OSError("o")


for k in range(3):
    try:
        fail(k)
    except Exception as e:
        copy = again(e, "copy")
        print(type(copy).__name__, repr(copy), type(copy) is type(e))
try:
    raise Pair("a", "b")
except Pair as e:
    try:
        print(type(e)("x"))
    except TypeError as t:
        print("TypeError:", t)


class Expect:
    def __init__(self, kind: type[BaseException]) -> None:
        self.kind = kind

    def __enter__(self) -> None:
        pass

    def __exit__(self, et: type[BaseException] | None, ev: BaseException | None, tb: object) -> bool:
        if et is None:
            print("nothing raised, expected", self.kind.__name__)
            return False
        print("got", et.__name__, "expected", self.kind.__name__, et is self.kind, issubclass(et, self.kind))
        return issubclass(et, self.kind)


with Expect(LookupError):
    raise KeyError("k")
with Expect(Quiet):
    raise Quiet("q")
with Expect(ValueError):
    pass
try:
    with Expect(ValueError):
        raise KeyError("not suppressed")
except KeyError as e:
    print("escaped", repr(e))


class Keyed(Exception):
    def __init__(self, text: str, *, code: int) -> None:
        super().__init__(text)
        self.code = code


try:
    raise Keyed("k", code=3)
except Keyed as e:
    try:
        raise type(e)("again")
    except TypeError as t:
        print("TypeError:", t)
