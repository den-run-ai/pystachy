# A generator suspended in try/except/finally (#490): a for loop that owns it closes it where the
# loop is left, by its end, break, return or an exception, before the code after the loop: its
# finally blocks run then, and so does except GeneratorExit, but not except Exception. The loop
# body's exceptions never enter the generator.
from collections.abc import Iterator


def guarded(n: int) -> Iterator[int]:
    print("  open")
    try:
        for i in range(n):
            yield i
    finally:
        print("  close")


def items() -> Iterator[int]:
    try:
        yield 1
        yield 2
    except Exception as e:
        print("generator saw", repr(e))
        yield 3
    finally:
        print("generator finally")


def layered() -> Iterator[str]:
    try:
        try:
            yield "a"
        finally:
            print("  inner finally")
        yield "b"
    except GeneratorExit:
        print("  GeneratorExit caught")
        raise
    finally:
        print("  outer finally")


for x in guarded(2):
    print("full", x)
for x in guarded(5):
    print("partial", x)
    if x == 1:
        break
print("after break")
try:
    for x in items():
        print("body", x)
        raise ValueError("from body")
except ValueError as e:
    print("caught", e)


def find(target: int) -> int:
    for x in items():
        if x == target:
            return x * 10
    return -1


print(find(2))
for s in layered():
    print("layered", s)
for s in layered():
    print("layered then break", s)
    break
for s in layered():
    if s == "b":
        break
for i, x in enumerate(guarded(3)):
    if i == 1:
        print("enumerate break")
        break
for x in guarded(3):
    for y in guarded(2):
        if y == 1:
            break
    if x == 1:
        break
for x in guarded(2):
    pass
else:
    print("else after the end")
for x in guarded(3):
    if x == 0:
        break
else:
    print("never")
print("done")


def nested() -> Iterator[int]:
    # a generator that owns the loop over another: closing the outer closes the inner first
    try:
        for x in guarded(3):
            yield x
    finally:
        print("  nested finally")


for v in nested():
    print("nested", v)
    if v == 1:
        break
