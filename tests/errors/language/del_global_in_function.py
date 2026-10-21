# error: local variable 'q' is read before its first assignment
# del q makes q a local of the function, which nothing assigns (CPython: UnboundLocalError)
q = 7


def k(flag: bool) -> int:
    if flag:
        del q
    return q


print("start")
print(k(False))
