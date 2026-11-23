# exceptions as values of object: printed, compared, tested and narrowed by isinstance() with a
# builtin exception class (to BaseException) or one of the program's (its object), and raised;
# a caught exception stored as object narrows to its class too
class AppError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"code {code}")
        self.code = code


def check(v: object) -> str:
    x: object = v
    if isinstance(x, AppError):
        return f"app {x.code} {x}"
    if isinstance(x, KeyError):
        return f"key {x!r}"
    if isinstance(x, Exception):
        return f"exception {type(x).__name__} {x}"
    return f"other {x}"


def main() -> None:
    errors: list[object] = [ValueError("bad"), AppError(7), KeyError("k"), 3, OSError("os")]
    for e in errors:
        print(check(e), repr(e), str(e), e == e, e is errors[0])
    first: object = errors[0]
    try:
        if isinstance(first, ValueError):
            raise first
    except ValueError as err:
        print("caught", err, err is first)
    app: object = errors[1]
    try:
        if isinstance(app, AppError):
            raise app
    except AppError as err:
        print("caught app", err.code)
    try:
        raise RuntimeError("boom")
    except RuntimeError as caught:
        kept: object = caught
        print(check(kept), isinstance(kept, RuntimeError), isinstance(kept, KeyError))
    for v in errors:
        try:
            print(len(v))
        except TypeError as e:
            print(e)
        try:
            print("%d" % v)
        except TypeError as e:
            print(e)


main()
