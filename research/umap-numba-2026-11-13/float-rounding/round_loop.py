import math
import sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000000
scale = float(sys.argv[2]) if len(sys.argv) > 2 else 0.37
t = 0
x = -12345.678
for k in range(n):
    x += scale
    t += math.floor(x) + round(x) - math.ceil(x) + math.trunc(x)
cells = [0] * 64
for k in range(n // 4):
    cells[int(math.floor((k * scale) % 64.0))] += 1
print(t, x, cells[0], cells[63])
