# Locals given values of several types (CPython keeps each value's own type): the join of
# their types, as if annotated, where the first type takes no later value.
def total(xs):
    t = 0
    for x in xs:
        t += x
    return t


def best_half(n: int):
    best = -1
    for i in range(n):
        if i % 2 == 0:
            best = i / 2
    return best


def last_none(n: int):
    x = 0
    for i in range(n):
        if i == 2:
            x = None
    return x


def label(n: int):
    v = n
    if n > 2:
        v = "many"
    return v


print(total([1, 2]), total([1.5, 2.5]), total([True, 2]))
print(best_half(5), best_half(0))
print(last_none(1), last_none(3))
print(label(1), label(5))
