# error: cannot infer what collect() returns: it calls itself before a use shows what the list it returns holds
def collect(n, *args):
    out = []
    for a in args:
        out.append(a)
    if n == 0:
        return out
    r: list[str] = collect(n - 1)
    print(r)
    return [1.5]


print(collect(1))
