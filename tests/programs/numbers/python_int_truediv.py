# pystachy: python-int
# Promoting ints (docs/python-int.md): true division of ints past 64 bits, rounded once as CPython
# rounds it: halfway cases to even, results at the ends of the float range, subnormals, signed
# zeros, and CPython's errors.


def show(a: int, b: int) -> str:
    try:
        return repr(a / b)
    except ZeroDivisionError as e:
        return "ZeroDivisionError: " + str(e)
    except OverflowError as e:
        return "OverflowError: " + str(e)


def num(i: int) -> int:
    # (operands from a function: containers hold 64-bit ints, docs/python-int.md)
    if i == 0:
        return 0
    if i == 1:
        return 1
    if i == 2:
        return -7
    if i == 3:
        return 2 ** 53 + 1
    if i == 4:
        return 2 ** 63
    if i == 5:
        return -(2 ** 64) - 1
    if i == 6:
        return 3 ** 100
    if i == 7:
        return -(10 ** 30) + 7
    if i == 8:
        return 2 ** 1023 + 2 ** 970
    if i == 9:
        return 2 ** 1024
    if i == 10:
        return 5 ** 700
    return -(2 ** 1100)


for i in range(12):
    print(num(i) % 1000, " ".join([show(num(i), num(j)) for j in range(12)]))

# halfway between two floats: to the even one; a bit more: up
for k in [60, 64, 80, 200, 1000]:
    half = 2 ** k + 2 ** (k - 53)
    print(k, show(half, 1), show(half + 1, 1), show(half + 2 ** (k - 53), 1), show(-half, 1), show(half * 3, 3), show(half, 2 ** 70))

# the subnormal range and the largest float
print(show(3, 2 ** 1074), show(1, 3 * 2 ** 1070), show(2 ** 60, 2 ** 1130), show(-1, 2 ** 1075), show(1, 2 ** 1076))
print(show(2 ** 1024 - 2 ** 970, 1), show(2 ** 1024 - 2 ** 970 - 1, 1), show(2 ** 1024 - 2 ** 971, 1), show(2 ** 2000, 2 ** 1000))
print(show(10 ** 400, 10 ** 399), show(10 ** 400 + 1, 10 ** 400), show(-(7 ** 300), 7 ** 299), show(2 ** 70, 2.0 ** 10 + 0.5 - 0.5 > 0))
x = 3 ** 90
y = 2 ** 70
print(x / y, y / x, x / 2.5, 2.5 / x, (x * x) / (y * y), (x / y) * y == x)
