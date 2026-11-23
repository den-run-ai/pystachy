# Documented deviation: repr(), str() and format() of a generator held by a Protocol value raise
# NotImplementedError (docs/language/compatibility.md#functions-and-object-identity). CPython
# prints the generator's address, <generator object numbers at 0x...>, which Pystachy does not
# print for any generator; the protocol's other operations work.
from typing import Iterator, Protocol


class Numbers(Protocol):
    def __iter__(self) -> Iterator[int]: ...


def numbers() -> Iterator[int]:
    yield 1
    yield 2


source: Numbers = numbers()
try:
    print(repr(source))
except NotImplementedError as e:
    print("NotImplementedError:", e)
try:
    print(f"{source}")
except NotImplementedError as e:
    print("NotImplementedError:", e)
print(list(source))
