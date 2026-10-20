# The set form of template_forward_cycle_annotated (#595)
def emptys(n):
    out = set()
    return out


def a(n):
    if n <= 0:
        return emptys(n)
    r: set[str] = b(n - 1)
    r.add("s" + str(n))
    return r


def b(n):
    return a(n)


print(sorted(a(3)))
q = b(2)
q.add("q")
print(sorted(q), "s1" in q, len(b(0)))
