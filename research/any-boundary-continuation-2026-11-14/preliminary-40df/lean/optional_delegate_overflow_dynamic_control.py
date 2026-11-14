# pystachy: dynamic-any
# pystachy: python-int
from typing import Iterator, Any

def child() -> Iterator[Any]:
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

def borrowed(value: Iterator[Any]) -> Iterator[int | None]:
    try:
        yield from value
    finally:
        print("borrowed closed")

a = owned()
try:
    print("owned first", next(a))
except OverflowError:
    print("owned overflow")
print("owned exhausted", next(a, None) is None)
b = child()
c = borrowed(b)
try:
    print("borrowed first", next(c))
except OverflowError:
    print("borrowed overflow")
print("borrowed exhausted", next(c, None) is None)
print("borrowed child next", next(b))
b.close()
