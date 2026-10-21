import sys


def check(n: int) -> int:
    if n < 0:
        sys.exit("fatal: bad input " + str(n))
    return n


print(check(2))
print(check(-1))
