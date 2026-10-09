n = 0
for i in range(1000000):
    s = str(i % 1000)
    n += len(s.zfill(8)) + len(s.ljust(6, "*")) + len(s.center(9))
print(n)
