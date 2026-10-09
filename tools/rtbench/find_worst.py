import sys
k = len(sys.argv)
h = "a" * (2000000 * k)
nd = "a" * 200000 + "b"
n = 0
for i in range(40):
    n += h.find(nd) + h.count(nd)
print(n)
