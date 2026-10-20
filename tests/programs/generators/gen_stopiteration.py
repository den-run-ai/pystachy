# PEP 479 (#490): a StopIteration that leaves a generator's body is a RuntimeError, "generator
# raised StopIteration"; a StopIteration raised in a for loop's body over a generator is not
# (the body's exceptions never enter the generator).
from collections.abc import Iterator


def plain() -> Iterator[int]:
    yield 1
    raise StopIteration("early")


def body_stop() -> Iterator[int]:
    yield 1
    yield 2


try:
    for x in plain():
        print("got", x)
except RuntimeError as e:
    print("RuntimeError:", e)
try:
    for x in body_stop():
        print("body", x)
        raise StopIteration("from the body")
except StopIteration as e:
    print("StopIteration:", e)
try:
    print(list(plain()))
except RuntimeError as e:
    print("list:", e)
for x in plain():
    print("last", x)
