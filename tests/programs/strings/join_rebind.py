# A variable that holds a list of ints and then lists that a function makes of floats: a list
# of int | float, which the function returns as if annotated.
def dot(a, b):
    s = 0
    for x, y in zip(a, b):
        s += x * y
    return s


def scale(u, k):
    return [x * k for x in u]


def ratio(n: int, rounds: int) -> float:
    u = [1] * n
    v = u
    for _ in range(rounds):
        v = scale(u, 0.5)
        u = scale(v, 1.5)
    return dot(u, v) / dot(v, v)


print(dot([1, 2], [3, 4]), dot([0.5], [2]))
print(ratio(4, 3), ratio(2, 0))
