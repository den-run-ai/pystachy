import math
n = 0
for i in range(300000):
    n += math.comb(60, i % 30) % 1000 + math.factorial(i % 20) % 7 + math.isqrt(i * 1000)
print(n)
