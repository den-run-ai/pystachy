# integer and float semantics that must match CPython exactly
import math

a = 17
b = -5
print(a + b, a - b, a * b, a // b, a % b, -a // 5, -a % 5, a // -b, a % -b)
print(7 // 2, -7 // 2, 7 % -3, -7 % -3, 0 // 5, 2 ** 10, 3 ** 0, (-2) ** 3)
print(a / 4, 1 / 3, 2 / 1, -7 / 2)
print(a & 12, a | 12, a ^ 12, ~a, 1 << 10, 1024 >> 3, -16 >> 2)
print(0x1F, 1_000_000, 0xff_ff)
x = 2.5
print(x * 2, x + 1, x - 0.5, x / 2, x // 2, x % 2, -x // 2, -x % 2, 2 ** 0.5, x ** 2)
print(7.5 // -2, 7.5 % -2, -7.5 % 2, 1e300 * 10, -1e300 * 10)
print(0.1, 0.2, 0.1 + 0.2, 1.0, 100.0, 1e16, 1e15, 1e-5, 0.0001, 123.456, -0.0, 1 / 7)
print(3.0 * 1e-7, 2.0 ** 60, 1e22, 1.5e300, 5e-324, 0.5, 2 / 3 * 3)
print(float("1.5"), float("inf"), float("-inf"), int("  42 "), int("-7"), int("ff", 16), int(3.99), int(-3.99))
print(abs(-3), abs(3), abs(-2.5), min(3, 1, 2), max(3, 1, 2), min(1.5, 0.5), max("a", "b"))
print(round(2.5), round(3.5), round(-2.5), round(2.675), round(7.0))
print(math.sqrt(16.0), math.floor(-2.5), math.ceil(2.1), math.pi, math.sin(0.0), math.cos(0.0))
print(math.exp(1.0), math.log(math.e), math.pow(2.0, 10.0), math.fabs(-1.25), math.atan2(1.0, 1.0))
print(1 < 2, 2 <= 2, 3 > 4, 1 == 1.0, 2 != 2, 1 < 2.5, 0.1 + 0.2 == 0.3)
print(1 < 2 < 3, 3 > 2 > 1 > 0, 1 < 3 < 2, 1 == 1 == 1)
print(True + True, True * 3, -True, True & False, True | False, True ^ True, int(True), float(False))
n = 1
for i in range(62):
    n = n * 2
print(n, n + (n - 1), -n - n)
big = 9223372036854775807
print(big, -big - 1, big % 1000, big // 1000000007)
s = 0.0
for i in range(1, 11):
    s += 1.0 / i
print(s, int(s * 1000), str(s)[:6])
h = 0
for c in "hash me":
    h = (h * 31 + ord(c)) & 0xFFFFFFFF
print(h)
print(10 % 3, -10 % 3, 10 % -3, 5.5 % 1.25)
