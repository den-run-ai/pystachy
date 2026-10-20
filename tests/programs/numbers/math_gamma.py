# math.gamma() and math.lgamma(), CPython's own Lanczos approximation (m_tgamma, m_lgamma), not
# libm's: every result is CPython's to the last bit. The special cases: gamma of 0, a negative
# integer or -inf, and lgamma of an integer <= 0, raise ValueError('math domain error'); a
# result too large raises OverflowError('math range error'); one that underflows is 0.0.
import math
from math import gamma, lgamma


def show(x: float) -> None:
    try:
        g = repr(gamma(x))
    except (ValueError, OverflowError) as e:
        g = type(e).__name__ + ": " + str(e)
    try:
        lg = repr(lgamma(x))
    except (ValueError, OverflowError) as e:
        lg = type(e).__name__ + ": " + str(e)
    print(repr(x), g, lg)


special = [0.0, -0.0, 1.0, 2.0, 3.0, 23.0, 24.0, -1.0, -2.0, -1e16, math.inf, -math.inf, math.nan,
           5e-324, -5e-324, 1e-20, 9.99e-21, -1e-21, 1e-300, 0.5, -0.5, 1.5, -1.5, 2.5, -2.5,
           5.5, 5.524680040776729, 5.6, 6.024680040776729, 139.5, 140.0, 140.5, 141.25, 170.5,
           171.0, 171.5, 171.62, 171.7, 172.0, 199.9, 200.0, 200.5, -139.5, -140.5, -150.5,
           -170.5, -171.5, -180.25, -199.5, -200.5, -1000.5, -1e10 - 0.5, 1e10, 1e300, 1.7976931348623157e308,
           -1.7976931348623157e308, 4503599627370495.5, -4503599627370495.5, 0.1, 0.01, -0.01, 1e-5]
for x in special:
    show(x)
# a sweep across the domain: below 5 the Lanczos sum is evaluated in x, from 5 on in 1/x
for i in range(-60, 121):
    show(i / 8.0 + 1.0 / 3.0)
for i in range(1, 41):
    show(i * 4.75 - 0.1)
    show(-i * 4.75 + 0.1)
print(gamma(5), gamma(True), lgamma(10), gamma(0.5) ** 2, math.gamma(1 / 3) * math.gamma(2 / 3))
total = 0.0
n = 0
x = 0.001
while x < 171.0:
    total += lgamma(x)
    n += 1
    x = x * 1.01 + 0.001
print(n, repr(total))
