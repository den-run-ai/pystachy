import sys
k = len(sys.argv)
xs = [w * k for w in ["12345", "12a45", "", "9", "000000000"]]
n = 0
for i in range(50000000):
    if xs[i % 5].isdigit():
        n += 1
print(n)
