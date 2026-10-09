parts = [str(i) for i in range(10000)]
n = 0
for i in range(300):
    n += len(",".join(parts))
print(n)
