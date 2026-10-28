# pystachy: python-int
# Function-local replay of inferred int storage, including a module without the pragma.
from fixed_retry import fixed_result, sum_results


def accumulate(count: int, step: int) -> int:
    total = 0
    for i in range(count):
        total += step
    return total


def chain(count: int, step: int) -> int:
    first = 0
    second = 0
    for i in range(count):
        first += step
        second += first
    return second


def positive(i: int) -> int:
    return 2 ** 70 + i


def negative(i: int) -> int:
    return -(2 ** 63) - i


print(accumulate(0, 2 ** 70), accumulate(3, 2 ** 70), accumulate(2, -(2 ** 63)))
print(chain(3, 2 ** 70), chain(3, -(2 ** 63)))
print(sum_results(positive, 4), sum_results(negative, 3))
print(fixed_result(lambda i: i + 1, 3))
