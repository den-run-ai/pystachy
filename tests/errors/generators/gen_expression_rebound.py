# error: a generator expression that reads 'k' is not supported where scale() may bind it again, or it may be unbound, before the generator runs (a generator expression reads it then)
def scale(xs: list[int]) -> list[int]:
    k = 2
    g = (x * k for x in xs)
    k = 3
    return list(g)


print(scale([1, 2]))
