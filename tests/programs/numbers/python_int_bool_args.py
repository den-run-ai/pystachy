# pystachy: python-int
# A bool given to an int parameter that the function reads only as a number (arithmetic,
# comparisons, truth, int(), float(), abs(), range() and the like) is the int it equals, which
# gives the bool's results; elsewhere it is rejected (tests/errors/numbers/python_int_bool_*.py)


def increment(n: int) -> int:
    return n + 1


def arith(x: int, k: int, f: float) -> float:
    return x * k + x / f - x // 2 + x % 2 + x ** 2 + (x << 3) + (x >> 1) + (x & 1) + (x | 0) + (x ^ 1) - x + +x


def truth(a: int, b: int) -> str:
    if a and not b:
        return "a"
    if a > b or a == 1 or b != 0:
        return "ab" if 0 <= a < 2 else "other"
    return "none"


def conv(x: int) -> str:
    return f"{int(x)} {float(x)} {abs(x)} {round(x)} {round(x, 2)} {hash(x)} {bool(x)} {range(x)} {chr(x + 64)} {hex(x)} {oct(x)} {bin(x)}"


def count(n: int) -> int:
    total = 0
    for i in range(n + 1):
        total += i + 1
    while n > 0:
        n -= 1
        total += 10
    return total


def big(x: int) -> int:
    return x + 2 ** 70 - (x * 2 ** 64)


def divide(x: int, y: int) -> str:
    try:
        return repr(x / y) + " " + repr(x // y) + " " + repr(x % y)
    except ZeroDivisionError as e:
        return "ZeroDivisionError: " + str(e)


def step(n: int = True) -> int:
    return n * 2


class Acc:
    def __init__(self, start: int) -> None:
        self.total = start + 0

    def add(self, k: int) -> int:
        self.total = self.total + k * 1
        return self.total

    @staticmethod
    def twice(k: int) -> int:
        return k * 2

    @property
    def value(self) -> int:
        return self.total

    @value.setter
    def value(self, v: int) -> None:
        self.total = v + 0


class Big(Acc):
    def add(self, k: int) -> int:
        self.total = self.total + k * 2 ** 70
        return self.total


flag = len("ab") > 1
print(increment(True), increment(False), increment(flag), increment(not flag), increment(n=True))
print(arith(True, 3, 2.0), arith(False, 3, 2.0), arith(flag, True, 0.5))
print(truth(True, False), truth(True, True), truth(False, False), truth(False, True))
print(conv(True))
print(conv(False))
print(count(True), count(False))
print(big(True), big(flag), big(False))
print(divide(True, True), divide(2 ** 70, flag), divide(True, False))
print(step(), step(False))
acc = Acc(True)
print(acc.add(True), acc.add(False), acc.total, Acc.twice(True))
acc.value = flag
print(acc.value)
for a in [Acc(0), Big(1)]:
    print(a.add(True), a.add(flag))
