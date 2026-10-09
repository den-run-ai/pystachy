import sys
k = len(sys.argv)
ws = ["ab", "ba:c", "x,y", "", "abc", " a ", "12", "a\nb"]
w2 = [w * k for w in ws]
t = 0
for i in range(5000000):
    w = w2[i % 8]
    t += len(w.ljust(8))
print(t)
