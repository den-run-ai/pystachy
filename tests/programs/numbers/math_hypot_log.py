# math.hypot is CPython's own algorithm (its last bit agrees, and it returns inf rather than
# raising on overflow); math.log(x, base) raises ZeroDivisionError for a base of 1 (see
# math_log_base_one.py).
import math

vals = [0.0, -0.0, 5e-324, 1e-310, 2.2250738585072014e-308, 1e-160, 0.1, 1.0, -3.0, 4.0, 1e154, 1e200,
        8.98846567431158e307, 1.7976931348623157e308, math.inf, -math.inf, math.nan]
for a in vals:
    print(" ".join([repr(math.hypot(a, b)) for b in vals]))
seed = 11


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


h = 0
for i in range(20000):
    a = (rnd() / 2147483648.0) * 2.0 ** (rnd() % 2040 - 1080)
    b = (rnd() / 2147483648.0) * 2.0 ** (rnd() % 2040 - 1080)
    s = math.hypot(a, b).hex()
    for c in s:
        h = (h * 131 + ord(c)) % 1000000007
print(h, math.hypot(2.718451619148254e+179, 6.73300831578672e+178).hex())
print(math.log(8.0, 2.0), math.log(2.0, 0.5), math.log(1.0, 2.0), math.log(math.inf, 2.0), math.log(2.0, math.inf), math.log(1e308, 1e-308))
