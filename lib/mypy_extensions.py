"""mypy_extensions as Pystachy compiles it: the names that mypy, and code written for mypyc,
import from it (python/mypy_extensions 1.2.0's API, not its code).

trait and mypyc_attr(...) are identity class decorators, as CPython runs them: the compiler
drops them where a class statement applies them (Loader.identity_decos), leaving the class
unchanged. The native integer names are int: CPython's i64(x) is int(x), and an annotation that
names one is an int's (Pystachy's int is a checked 64-bit integer, a valid i64; it does not wrap
u8 or i32, as CPython's int does not). They are aliases of int here, so i64 is int and
i64.__name__ is 'int', where CPython's are distinct classes.
"""
from typing import Callable, TypeVar

_T = TypeVar("_T")


def trait(cls: _T) -> _T:
    return cls


def mypyc_attr(*attrs: str, **kwattrs: object) -> Callable[[_T], _T]:
    return lambda x: x


i64 = int
i32 = int
i16 = int
i8 = int
u64 = int
u32 = int
u16 = int
u8 = int
