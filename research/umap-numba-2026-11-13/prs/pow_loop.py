"""Float powers in loops: x ** e, pow() and math.pow() with run-time operands."""
import math
import sys

rounds = int(sys.argv[1])
xs = [1.0 + (i % 1000) * 0.001 for i in range(1000)]
e = 1.5 + 0.0 * len(sys.argv)
s = 0.0
t = 0.0
for k in range(rounds):
    for i in range(1000):
        s += xs[i] ** e
        t += math.pow(xs[i], -e)
print(repr(s), repr(t))
