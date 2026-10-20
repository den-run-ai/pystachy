# A chained assignment whose first target is a dict item and whose second is a joined variable:
# the call's fresh list is the second target's value too, so the function returns the joined
# list type, as for u = scale(u, 0.5) alone (join_rebind.py).
def scale(u, k):
    return [x * k for x in u]


def run(n: int, rounds: int):
    u = [1] * n
    seen = {}
    for i in range(rounds):
        seen[i] = u = scale(u, 0.5)
    return u, seen


print(run(2, 2), run(1, 0))
