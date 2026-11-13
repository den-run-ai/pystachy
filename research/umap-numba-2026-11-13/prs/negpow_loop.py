"""Powers of bases of either sign with integral exponents, as squared errors make them."""
import sys

rounds = int(sys.argv[1])
xs = [1.0 + (i % 1000) * 0.001 for i in range(1000)]
two = 2.0 + 0.0 * len(sys.argv)
s = 0.0
for k in range(rounds):
    for i in range(1000):
        s += (xs[i] - 1.5) ** two + (1.25 - xs[i]) ** 3.0
print(repr(s))
