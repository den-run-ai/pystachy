# pystachy: dynamic-any
# pystachy: python-int
from typing import Iterator

def child() -> Iterator[int]:
    try:
        try:
            yield 7
        except ValueError:
            yield 2 ** 80
            yield 9
    finally:
        print("child closed")

def owned() -> Iterator[int | None]:
    try:
        yield from child()
    finally:
        print("owned closed")

def borrowed(source: Iterator[int]) -> Iterator[int | None]:
    try:
        yield from source
    finally:
        print("borrowed closed")

g = owned()
print("owned first", next(g))
try:
    g.throw(ValueError("wide"))
except OverflowError:
    print("owned overflow")
print("owned done", next(g, None) is None)
inner = child()
outer = borrowed(inner)
print("borrowed first", next(outer))
try:
    outer.throw(ValueError("wide"))
except OverflowError:
    print("borrowed overflow")
print("borrowed next", next(inner))
inner.close()
