# Iterator classes and exceptions: StopIteration (or a subclass, or one a nested next() raises)
# ends a loop; anything else __next__ raises leaves it, through try/finally; break, continue,
# return and else; a loop over an exhausted iterator; and the exception being handled, which a
# loop's own StopIteration leaves as it was. A StopIteration that the loop's body raises
# propagates, as does an exception from __iter__.


class Count:
    def __init__(self, n: int, fail: int = -1) -> None:
        self.i = 0
        self.n = n
        self.fail = fail

    def __iter__(self) -> "Count":
        print("iter")
        return self

    def __next__(self) -> int:
        if self.i == self.fail:
            raise ValueError(f"bad item {self.i}")
        if self.i >= self.n:
            print("stop")
            raise StopIteration
        self.i += 1
        return self.i


class MyStop(StopIteration):
    pass


class Stops:
    def __init__(self) -> None:
        self.k = 0

    def __iter__(self):
        return self

    def __next__(self) -> str:
        self.k += 1
        if self.k > 2:
            raise MyStop("done")
        return "s" * self.k


class Wrap:
    # its items are another iterator's: next() of it raises the StopIteration that ends both
    def __init__(self, inner: Count) -> None:
        self.inner = inner

    def __iter__(self):
        return self

    def __next__(self) -> int:
        return next(self.inner) * 10


class NoIter:
    # an iterator without __iter__: a for statement takes it from another object's __iter__
    def __init__(self) -> None:
        self.k = 0

    def __next__(self) -> int:
        self.k += 1
        if self.k > 2:
            raise StopIteration
        return self.k


class Holder:
    def __iter__(self) -> NoIter:
        return NoIter()


def first_big(it: Count) -> int:
    for x in it:
        if x > 1:
            return x
    return -1


class Stepper:
    # __iter__ may raise; __next__'s StopIteration comes from a method it calls
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self):
        if self.n < 0:
            raise ValueError("negative")
        return self

    def __next__(self) -> int:
        return self.step()

    def step(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


def body_stop() -> None:
    # a StopIteration the loop's body raises is not the end of the items: it propagates
    for x in Stepper(3):
        print("x", x)
        if x == 2:
            raise StopIteration("from body")


def find(n: int) -> int:
    try:
        for x in Stepper(5):
            if x == n:
                return x * 100
    finally:
        print("finally", n)
    return -1


def reraise() -> None:
    raise


try:
    try:
        for x in Count(5, 2):
            print("got", x)
    finally:
        print("finally")
except ValueError as e:
    print("ValueError", e)
try:
    print(list(Count(3, 1)))
except ValueError as e:
    print("list: ValueError", e)
try:
    print(2 in Count(4, 1))
except ValueError as e:
    print("in: ValueError", e)
for s in Stops():
    print(s)
print(list(Stops()), next(Stops()), next(Stops(), "default"))
print(list(Wrap(Count(3))), sum(Wrap(Count(2))))
for v in Holder():
    print("holder", v)
c = Count(4)
print(first_big(c), list(c))
for x in c:
    print("never")
else:
    print("exhausted")
for x in Count(2):
    print("loop", x)
else:
    print("else after", x)
for x in Count(3):
    if x == 2:
        break
else:
    print("not printed")
for x in Count(3):
    try:
        if x == 1:
            continue
        if x == 3:
            break
        print("body", x)
    finally:
        print("cleanup", x)
c2 = Count(6)
for x in c2:
    for y in c2:
        print(x, y)
        if y >= x + 2:
            break
print(list(zip(Count(3), Count(1))))
print(list(zip([7, 8, 9], Count(2))))
print(list(enumerate(Count(2), start=5)))
try:
    raise KeyError("k")
except KeyError:
    for x in Count(1):
        pass
    try:
        raise
    except KeyError as e:
        print("reraised", e)
try:
    raise IndexError("i")
except IndexError:
    print(sum(Count(2)), next(Count(0), -1))
    try:
        reraise()
    except IndexError as e:
        print("reraised again", e)
it = Count(3)
try:
    print(next(it), next(it), next(it), next(it))
except StopIteration:
    print("caught StopIteration")
try:
    print(next(it))
except StopIteration as e:
    print("caught again", type(e).__name__, repr(e))
try:
    s3 = Stops()
    print(next(s3), next(s3), next(s3))
except StopIteration as e:
    print("caught", type(e).__name__, e)
print(next(Count(0), None), next(Count(1), None))
f = lambda: [x + 1 for x in Count(2)]
print(f())
for x in Count(3):
    try:
        if x == 2:
            raise RuntimeError("in body")
        print("ok", x)
    except RuntimeError as e:
        print("handled", e)
try:
    a, b = Count(3)
except ValueError as e:
    print("ValueError:", e)
try:
    a, b, d = Count(1)
except ValueError as e:
    print("ValueError:", e)
try:
    a, b = Count(5, 1)
except ValueError as e:
    print("ValueError:", e)
try:
    body_stop()
except StopIteration as e:
    print("propagated", e)
try:
    for x in Stepper(-1):
        print(x)
except ValueError as e:
    print("iter failed", e)
li = iter([1, 2])
try:
    for y in [10, 20, 30]:
        print(y, next(li))
except StopIteration:
    print("next in body propagated")
print(find(3), find(9))
total = 0
for a in Stepper(3):
    for b in Stepper(a):
        if b == 2:
            continue
        total += a * b
print(total)
print([x for x in Stepper(4) if x % 2 == 0], sum(x * x for x in Stepper(3)))
print(sorted(Stepper(3), key=lambda v: -v), max(Stepper(4), key=lambda v: v % 3))
print(next(Count(1)))
print(next(Count(0)))
