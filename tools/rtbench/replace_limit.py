# Bounded replacements cross the dense threshold with small, medium and near-full counts.
# Counting must stop early while keeping the throughput of the unlimited counting loop.
s = "*" * 10000000
n = 0
for count in (65537, 1000000, 9999999):
    for _ in range(7):
        r = s.replace("*", "", count)
        n += len(r) + ord(r[-1])
print(n)
