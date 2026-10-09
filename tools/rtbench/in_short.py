import sys
k = len(sys.argv)
words = [w * k for w in ["alpha", "beta", "gamma", "delta", "epsilon"]]
n = 0
for i in range(20000000):
    if "mm" in words[i % 5]:
        n += 1
print(n)
