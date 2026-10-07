def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def gcd(a: int, b: int) -> int:
    while b != 0:
        t = a % b
        a = b
        b = t
    return a


print(fib(20), gcd(1071, 462))
print(7 // 2, -7 // 2, 7 // -2, -7 // -2)
print(7 % 3, -7 % 3, 7 % -3, -7 % -3)
print(1 << 40, -17 >> 2, 6 & 3, 6 | 3, 6 ^ 3)
print(2 + 3 * 4 - 5, (2 + 3) * 4, -(3 - 5), 10 - 2 - 3)
print(0x7F, 0xff, 1000000007 * 1000000007 % 998244353)
print(3 < 4, 3 >= 4, 3 == 3, 3 != 3, not 3 < 4)
print(True and False, True or False, not True, 1 < 2 and 2 < 3)
print(abs(-5), min(3, 9), max(3, 9), int("-123") + 1)
x = 5
x += 3
x *= 2
x -= 1
x //= 2
x %= 5
x <<= 3
x |= 1
print(x)
total = 0
for i in range(10):
    if i == 3:
        continue
    if i == 8:
        break
    total += i
print(total, i)
for i in range(3, 6):
    for j in range(i):
        total += j
print(total)
n = 0
while True:
    n += 1
    if n * n > 200:
        break
print(n, -9223372036854775807 - 1, 9223372036854775807)
n = 64
print(5 >> n, -5 >> n, 5 >> 63, -1 >> 200, 7 >> 0, 7 << 0, 1 << 62, 3 << 61, 0 << n)
m = 0
m <<= 70
k = -100
k >>= 70
print(m, k, (1 << 62) - 1 + (1 << 62))
assert 2 + 2 == 4
assert m == 0, "shifted out"
print(int("42"), int("+7"), int("-0"), str(-9223372036854775807 - 1), chr(0x41) + chr(122))
