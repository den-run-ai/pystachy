# Closing a generator its loop owns (#490): what the close raises, and a generator that ignores
# GeneratorExit and yields again, are reported on stderr as CPython reports exceptions it ignores
# ("Exception ignored in: <generator object ...>"), and the break, return or exception of the
# loop goes on. Only the last stderr line is compared: the last report's exception.
from collections.abc import Iterator


def stubborn() -> Iterator[int]:
    while True:
        try:
            yield 1
        except GeneratorExit:
            print("ignoring close")


def noisy() -> Iterator[int]:
    try:
        yield 1
    finally:
        raise KeyError("cleanup")


class Oops(Exception):
    pass


def oops() -> Iterator[int]:
    try:
        yield 1
    finally:
        raise Oops("custom")


for x in stubborn():
    break
print("after break")
try:
    for x in noisy():
        raise ValueError("from body")
except ValueError as e:
    print("caught", repr(e))


def first() -> int:
    for x in noisy():
        return 7
    return -1


print(first())
for x in oops():
    break
print("after oops")
for x in noisy():
    break
print("end")
