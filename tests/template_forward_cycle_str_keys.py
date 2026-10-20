# The dict form of template_forward_cycle_annotated: str keys through the function that returns
# a(n) unchanged, also in its result after the cycle (#595)
def emptyd(n):
    out = {}
    return out


def a(n):
    if n <= 0:
        return emptyd(n)
    if n == 1:
        return b(n - 1)
    r: dict[str, float] = b(n - 1)
    r["k" + str(n)] = n * 0.5
    return r


def b(n):
    return a(n)


print(a(4))
q = b(4)
print(q, q["k3"], "k9" in q, b(1))
q["z"] = 9.5
print(sorted(q))
