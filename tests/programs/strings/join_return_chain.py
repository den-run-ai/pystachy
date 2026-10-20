# Functions without a return annotation that return another one's fresh list where a joined list
# is kept: each returns the joined list type, as if annotated (the values keep their types).
def scale(u, k):
    return [x * k for x in u]


def twice(u):
    return scale(scale(u, 0.5), 2.0)


def run(n: int, rounds: int):
    u = [1] * n
    for _ in range(rounds):
        u = twice(u)
    return u


print(run(3, 2), run(2, 0), run(0, 1))
