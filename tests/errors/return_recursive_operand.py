# error: cannot infer what fact() returns: its recursive return type is unresolved; annotate its return type
def fact(n: int):
    return 1 if n <= 1 else n * fact(n - 1)

print(fact(5))
