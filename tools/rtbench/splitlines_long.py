import sys
k = len(sys.argv)
s = ("x" * (1000 * k) + "\n") * (10000 * k)
t = 0
for i in range(10):
    t += len(s.splitlines()) + len(s.splitlines(True))
print(t)
