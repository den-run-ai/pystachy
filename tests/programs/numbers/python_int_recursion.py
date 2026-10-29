# pystachy: python-int
# Annotated recursive functions and methods. The int annotation names one static
# type, so a function that calls itself before its first return compiles.


def factorial(n: int) -> int:
    return 1 if n < 2 else n * factorial(n - 1)


def gcd(a: "int", b: "int") -> "int":
    if b == 0:
        return a
    return gcd(b, a % b)


def doubled(n: int) -> int:
    if n == 0:
        return 1
    return 2 * doubled(n - 1)


def is_even(n: int) -> bool:
    return True if n == 0 else is_odd(n - 1)


def is_odd(n: int) -> bool:
    return False if n == 0 else is_even(n - 1)


def fib(n: int, memo: dict[int, int]) -> int:
    if n < 2:
        return n
    if n in memo:
        return memo[n]
    value = fib(n - 1, memo) + fib(n - 2, memo)
    memo[n] = value
    return value


class Counter:
    def __init__(self, base: int) -> None:
        self.base = base

    def climb(self, n: int) -> int:
        return self.base if n == 0 else self.climb(n - 1) * 3


print(factorial(20), factorial(30))
print(gcd(2 ** 100, 6 ** 40), gcd(48, 18))
print(doubled(70), doubled(3))
print(is_even(10), is_odd(7))
print(fib(100, {}))
print(Counter(2 ** 63).climb(5))
