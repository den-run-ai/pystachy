import sys
k = len(sys.argv)
words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda", "mu"]
parts = []
x = 7 * k
for i in range(30000):
    x = (x * 1103515245 + 12345) % 2147483648
    line = ""
    for w in range(2 + (x >> 8) % 10):
        x = (x * 1103515245 + 12345) % 2147483648
        line += words[(x >> 12) % len(words)] + ","
    parts.append(line + "\n")
t = "".join(parts)
n = 0
for r in range(40):
    i = 0
    j = t.find(",")
    while j >= 0:
        n += j - i
        i = j + 1
        j = t.find(",", i)
    i = 0
    j = t.find("\n")
    while j >= 0:
        n += j - i
        i = j + 1
        j = t.find("\n", i)
print(n)
