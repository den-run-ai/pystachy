def arity(*args) -> int:
    return len(args)


def checks(k: int) -> list[int]:
    def g(x: int) -> int:
        return x + k

    total = 0
    stack = 0
    for i in range(20):
        t = (g, i, i, i, i, i, i, i)
        total += len(t)
        stack += arity(g, i, i, i, i, i, i, i, i, i, i, i) + k * 3
    values = (g, 5, 6, 7)
    read = values[0](values[1]) + values[2] + values[3]
    last = (1, 2, g)
    final = last[2](last[0]) + last[1] + len(last)
    fn = lambda x: x + k
    nested = ((fn, 4), (g, 5))
    return [total, stack, read, final, nested[0][0](nested[0][1]), nested[1][0](nested[1][1])]
