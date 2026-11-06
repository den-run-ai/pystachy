# The typed twin of boxes.py: N ints in a list[int]
import sys

n = int(sys.argv[1])
xs: list[int] = []
for i in range(n):
    xs.append(i + 1000)
print(len(xs), xs[-1])
