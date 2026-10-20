# for and while loops with an else block: it runs when the loop ends without break
def find(xs: list[int], t: int) -> int:
    for i in range(len(xs)):
        if xs[i] == t:
            break
    else:
        return -1
    return i


def primes(n: int) -> list[int]:
    out: list[int] = []
    for k in range(2, n):
        for d in out:
            if k % d == 0:
                break
        else:
            out.append(k)
    return out


n = 0
while n < 3:
    n += 1
    if n == 10:
        break
else:
    print("while else ran", n)
while True:
    break
else:
    print("never")
for x in [0][1:]:
    pass
else:
    print("empty for else")
for c in "abc":
    for d in "xyz":
        if d == "y":
            break
    else:
        print("inner else never")
    if c == "b":
        break
else:
    print("outer else never")
print(find([5, 6, 7], 6), find([5], 9), primes(30), c)
