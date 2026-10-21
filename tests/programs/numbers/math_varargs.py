# math.gcd(*integers), math.lcm(*integers) and math.hypot(*coordinates) of any number of
# arguments (gcd() is 0, lcm() 1, hypot() 0.0; of one, its absolute value), math.perm(n) and
# perm(n, None) (n!), and bools where the integer functions take ints (#324).
import math
from math import gcd, hypot, lcm

print(gcd(), gcd(0), gcd(-12), gcd(12), gcd(120, 84, 102), gcd(120, 84, 102, 1, 5), gcd(0, 0, 0), gcd(0, -7, 0))
print(gcd(-9223372036854775807), gcd(9223372036854775807, 2, 3), gcd(2 ** 62, -2 ** 61, 2 ** 40))
print(lcm(), lcm(0), lcm(-120), lcm(120, 0, 84), lcm(4, 6, 10), lcm(2, 3, 5, 7, 11, 13), lcm(-4, -6, 0, 8))
print(lcm(0, 9223372036854775807, 9223372036854775807), lcm(3, 9223372036854775807 // 3 * 3))
print(hypot(), hypot(3.0), hypot(-3.0), hypot(-0.0), hypot(1.5, 1.5, 0.5), hypot(1, 2, 2), hypot(2, 3, 6, 0))
print(hypot(1e308, 1e308, 1e308), hypot(5e-324, 5e-324, 5e-324), hypot(math.inf), hypot(-math.inf, math.nan, 1.0))
print(hypot(math.nan), hypot(math.nan, 1.0, 2.0), hypot(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0))
print(hypot(True, 2, 3), hypot(False), hypot(1, 1, 1), hypot(0.1, 0.2, 0.3) == math.dist((0.1, 0.2, 0.3), (0.0, 0.0, 0.0)))
print(math.perm(5), math.perm(5, None), math.perm(0), math.perm(20), math.perm(True), math.perm(5, 2))
try:
    print(math.perm(-1))
except ValueError as e:
    print("ValueError", e)
try:
    print(math.perm(-1, None))
except ValueError as e:
    print("ValueError", e)
print(math.comb(True, False), math.comb(5, True), math.isqrt(True), math.factorial(True), math.factorial(False))
print(gcd(True, 4), gcd(False, 6), lcm(True, 4), lcm(True), gcd(True), math.perm(True, True), math.comb(False, True))


# arguments are evaluated in order before the call
def num(tag: str, v: int) -> int:
    print("eval", tag, end="; ")
    return v


print(gcd(num("a", 12), num("b", 18), num("c", 8)))
print(lcm(num("a", 0), num("b", 18), num("c", 8)))
print(hypot(num("x", 3), num("y", 4), num("z", 12)))
f = math.gcd
g = math.hypot
print(f(), f(6, 10, 15), g(), g(1.0), g(2.0, 3.0, 6.0))
