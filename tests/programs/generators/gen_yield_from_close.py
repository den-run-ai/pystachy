# A generator suspended in yield from that its loop closes (#490): the generator it delegates to
# is closed first, and what that raises is raised in the delegating generator at the yield from,
# whose handlers see it (PEP 380), as CPython closes them; what then leaves the delegating
# generator is reported as an exception CPython ignores. Only the last stderr line is compared.
from collections.abc import Iterator


def noisy() -> Iterator[int]:
    try:
        yield 1
        yield 2
    finally:
        print("noisy closing")
        raise KeyError("cleanup")


def tolerant() -> Iterator[int]:
    try:
        yield from noisy()
    except KeyError as e:
        print("tolerant caught", repr(e))
    print("tolerant ends")


for x in tolerant():
    print("got", x)
    break
print("after break")


def stubborn() -> Iterator[int]:
    try:
        yield 1
    except GeneratorExit:
        yield 2


def wraps_stubborn() -> Iterator[int]:
    try:
        yield from stubborn()
    finally:
        print("wraps_stubborn finally")


for x in wraps_stubborn():
    break
print("after stubborn")


def plain_outer() -> Iterator[int]:
    yield from noisy()


try:
    for x in plain_outer():
        raise ValueError("body")
except ValueError as e:
    print("caught", repr(e))
print("end")
