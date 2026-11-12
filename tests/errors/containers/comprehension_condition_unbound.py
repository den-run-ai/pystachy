# error: comprehension_condition_unbound.py:4: error: a closure captures 'y' before the comprehension's for clause binds it
def f(xs: list[int], y: int) -> list[int]:
    # (a lambda in a condition reads the comprehension's y too)
    return [x for x in xs if (lambda: y)() for y in xs]


print(f([1, 2], 0))
