import sys
k = len(sys.argv)
xs = [w * k for w in ["  a  ", "\tbb\n", "c", "  dd", "ee  "]]
n = 0
for i in range(3000000):
    n += len(xs[i % 5].strip())
print(n)
