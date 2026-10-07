# prime sieve over a large list[bool], plus list building
def sieve(n: int) -> int:
    flags = [True] * (n + 1)
    flags[0] = False
    flags[1] = False
    i = 2
    while i * i <= n:
        if flags[i]:
            for j in range(i * i, n + 1, i):
                flags[j] = False
        i += 1
    count = 0
    for f in flags:
        if f:
            count += 1
    return count


total = 0
for rep in range(3):
    total += sieve(4000000)
print(total)
