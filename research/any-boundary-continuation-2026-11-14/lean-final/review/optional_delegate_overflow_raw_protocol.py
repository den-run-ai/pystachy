# pystachy: dynamic-any
# pystachy: python-int
from typing import Iterator

def child() -> Iterator[int]:
    try:
        print("child entered")
        yield 2 ** 80
        print("child resumed")
        yield 3
    finally:
        print("child closed")

def owned() -> Iterator[int | None]:
    try:
        yield from child()
    finally:
        print("owned closed")

def borrowed(value: Iterator[int]) -> Iterator[int | None]:
    try:
        yield from value
    finally:
        print("borrowed closed")

a = owned()
try:
    print("owned first", a.send(None))
except OverflowError:
    print("owned overflow")
print("owned exhausted", next(a, None) is None)
b = child()
c = borrowed(b)
try:
    print("borrowed first", c.send(None))
except OverflowError:
    print("borrowed overflow")
print("borrowed exhausted", next(c, None) is None)
print("borrowed child next", next(b))
b.close()
