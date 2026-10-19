# Exception classes as values: class objects of the builtin classes and of the program's, which
# compare and hash by identity, print as CPython's, and are kept in containers, tested with
# issubclass() and isinstance(), called and raised


class AppError(Exception):
    pass


class NotFound(AppError):
    pass


class Coded(AppError):
    def __init__(self, msg: str, code: int = 7):
        super().__init__(msg)
        self.code = code


def show(c: type[BaseException]) -> str:
    return c.__name__ + " " + c.__qualname__ + " " + c.__module__


k = KeyError
print(k)
print(repr(ValueError), str(AppError), f"{NotFound}")
print(k is KeyError, k is ValueError, k == KeyError, k != KeyError, k == 5)
print(IOError is OSError, EnvironmentError == OSError)
print(show(KeyError), show(AppError), show(NotFound))
classes = [KeyError, ValueError, AppError]
print(classes)
print(ValueError in classes, TypeError in classes, classes.index(AppError))
seen = {KeyError: "k", AppError: "a"}
print(seen[KeyError], seen.get(TypeError, "-"), len(seen))
print({KeyError, KeyError, ValueError} == {ValueError, KeyError})
print(hash(KeyError) == hash(KeyError), hash(KeyError) == hash(ValueError))
counts: dict[type[BaseException], int] = {}
for c in [KeyError, ValueError, KeyError, NotFound]:
    counts[c] = counts.get(c, 0) + 1
print(counts)
registry = {("text", UserWarning, 3): True}
print(("text", UserWarning, 3) in registry, ("text", DeprecationWarning, 3) in registry)
print(issubclass(KeyError, LookupError), issubclass(k, Exception), issubclass(k, ValueError))
base = LookupError
print(issubclass(KeyError, base), issubclass(NotFound, AppError), issubclass(AppError, NotFound))
print(issubclass(NotFound, (ValueError, AppError)), issubclass(ValueError, (KeyError, AppError)))
group = (TypeError, NotFound)
print(issubclass(NotFound, group), issubclass(AppError, group), issubclass(k, (base, group)))
print(isinstance(KeyError, type), isinstance(AppError, type), isinstance(5, k), isinstance("x", group))
try:
    raise KeyError("x")
except Exception as e:
    print(isinstance(e, k), isinstance(e, base), isinstance(e, AppError), isinstance(e, group))
    t = type(e)
    print(t is KeyError, t is k, t, t.__name__, t in seen)
try:
    raise NotFound("nf")
except AppError as e:
    print(type(e) is NotFound, type(e) is AppError, issubclass(type(e), AppError), isinstance(e, group))
e2 = k("missing")
print(repr(e2), str(e2))
for c in [ValueError, KeyError, SystemExit, OSError, SyntaxError, StopIteration]:
    print(repr(c()), repr(c("")), repr(c("x")), repr(c(3)), repr(str(c(None))))
se = SystemExit
print(repr(se(True)), repr(se(None)), str(se(None)), repr(se(2)), str(se("bye")))
for c in [ValueError, KeyError, AppError, NotFound, Coded]:
    try:
        raise c("boom")
    except LookupError as e:
        print("lookup", repr(e))
    except AppError as e:
        print("app", type(e).__name__, str(e), repr(e))
    except Exception as e:
        print("other", repr(e))
for c in [ValueError, NotFound]:
    try:
        raise c
    except Exception as e:
        print("bare", repr(e), type(e) is c)


def check(value: int, error: type[Exception] = ValueError) -> int:
    if value < 0:
        raise error(f"negative: {value}")
    return value


for v in [1, -1]:
    for err in [ValueError, AppError]:
        try:
            print(check(v, err))
        except Exception as e:
            print(type(e).__name__, e)
try:
    print(check(-2))
except ValueError as e:
    print("default", e)


def warn(message: str, category: type[Warning] | None = None) -> None:
    if category is None:
        category = UserWarning
    if not issubclass(category, Warning):
        raise TypeError("category must be a Warning subclass")
    w = category(message)
    print(f"{category.__name__}: {w}", isinstance(w, Warning), isinstance(w, category))


warn("a")
warn("b", DeprecationWarning)
try:
    print(sorted([KeyError, ValueError]))
except TypeError as e:
    print("TypeError:", e)
try:
    raise RuntimeError("outer") from KeyError
except RuntimeError as e:
    print(repr(e), repr(e.__cause__))
