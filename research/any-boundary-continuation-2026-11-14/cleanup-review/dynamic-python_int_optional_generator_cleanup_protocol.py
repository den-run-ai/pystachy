# pystachy: dynamic-any
# pystachy: python-int
# Optional yields have the checked 64-bit boundary in docs/python-int.md.
# Unlike CPython, a wide delegated int raises OverflowError. That edge destroys
# an owned delegate before the wrapper handles it, but preserves a borrowed one.
from typing import Any, Iterator


def child(value: int, first: bool) -> Iterator[Any]:
    try:
        print("child entered")
        if first:
            yield 7
        yield value
        print("child resumed")
        yield 9
    finally:
        print("child finally")


def owned(value: int, first: bool) -> Iterator[int | None]:
    try:
        yield from child(value, first)
    except OverflowError:
        print("owned caught")
        raise
    finally:
        print("owned finally")


def borrowed(source: Iterator[Any]) -> Iterator[int | None]:
    try:
        yield from source
    except OverflowError:
        print("borrowed caught")
        raise
    finally:
        print("borrowed finally")


for value in [2 ** 63, -2 ** 63 - 1]:
    for first in [False, True]:
        print("case", value, first)
        outer = owned(value, first)
        if first:
            print("owned first", outer.send(None))
        try:
            print("owned wide", outer.send(None))
        except OverflowError:
            print("owned overflow")
        print("owned done", next(outer, None) is None)
        print("owned done again", next(outer, None) is None)

        inner = child(value, first)
        wrapper = borrowed(inner)
        if first:
            print("borrowed first", wrapper.send(None))
        try:
            print("borrowed wide", wrapper.send(None))
        except OverflowError:
            print("borrowed overflow")
        print("borrowed done", next(wrapper, None) is None)
        print("borrowed next", next(inner, None))
        print("borrowed child done", next(inner, None) is None)
        print("borrowed done again", next(wrapper, None) is None)
