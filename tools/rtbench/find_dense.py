import sys
k = len(sys.argv)
h = "abcdefghij klmnopq\n" * (500000 * k)
n = 0
for i in range(40):
    n += h.find("abcdefghij klmnopq\nX") + h.rfind("zz")
print(n)
