# Documented dynamic annotation deviation (docs/dynamic-any.md): a concrete
# generator yield channel checks Any values, as other concrete annotations do.
# CPython ignores the annotation; Pystachy raises without losing owned cleanup
# or closing a generator that the caller still owns.
# pystachy: dynamic-any
from typing import Any, Iterator


def dynamic(label: str) -> Iterator[Any]:
    try:
        yield "wrong"
        yield 42
    finally:
        print(label, "cleanup")


def owned() -> Iterator[int]:
    try:
        yield from dynamic("owned")
    finally:
        print("outer cleanup")


o = owned()
try:
    print(next(o))
except TypeError as error:
    print(error)
o.close()

existing = dynamic("borrowed")


def borrowed() -> Iterator[int]:
    yield from existing


b = borrowed()
try:
    print(next(b))
except TypeError as error:
    print(error)
print("retained", next(existing))
existing.close()
