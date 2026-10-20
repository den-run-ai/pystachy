"""A program's own module called ffi (tests/programs/language/ffi_own.py): on the module path, it comes before
Pystachy's builtin ffi, as it comes first under CPython, whatever names it defines"""
c_int = 7


def extern(n: int) -> int:
    return n + 1


def export(n: int) -> int:
    return n * 2


def string_at(a: int, n: int) -> str:
    return str(a) * n


def track(a: int, b: int) -> int:
    return a - b


def untrack(i: int) -> None:
    print("untrack", i)


def collected() -> int:
    return 3
