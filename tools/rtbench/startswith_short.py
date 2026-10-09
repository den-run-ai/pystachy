import sys
k = len(sys.argv)
xs = [w * k for w in ["prefix_a", "prefix_b", "other", "pre", "prefix"]]
n = 0
for i in range(50000000):
    if xs[i % 5].startswith("prefix"):
        n += 1
print(n)
