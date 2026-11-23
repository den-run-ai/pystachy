# pystachy: python-int
# A recursive alias's int member is a 64-bit int, also where a type argument names it in a
# module whose ints promote.
type Value[F] = str | F | list[Value[F]] | dict[str, Value[F]]


def f(v: Value[int]) -> int:
    if isinstance(v, int):
        return v + 1
    if isinstance(v, list):
        return sum([f(x) for x in v])
    return 0


print(f([1, 2, [3, "s"]]), 2**70 + f(1))
