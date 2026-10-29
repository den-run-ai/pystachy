# The same documented annotation deviation after throw() resumes a delegate:
# a failed Any yield conversion still drops the directly owned generator.
# pystachy: dynamic-any
from typing import Any, Generator


def recovery() -> Generator[Any, None, None]:
    try:
        try:
            yield 1
        except ValueError:
            yield "wrong"
    finally:
        print("recovery cleanup")


def concrete() -> Generator[int, None, None]:
    yield from recovery()


it = concrete()
print(next(it))
try:
    print(it.throw(ValueError("recover")))
except TypeError as error:
    print(error)
it.close()
