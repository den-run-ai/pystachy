import math
n = 0
for i in range(1, 3000000):
    n += math.gcd(i * 7919, 1000003 * (i % 97 + 1))
print(n)
