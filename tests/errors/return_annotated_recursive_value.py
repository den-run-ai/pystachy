# error: cannot infer what recursive() returns: recursion already used None; annotate its return type
def recursive(n: int):
    if n > 0:
        return recursive(n - 1)
    return 1

print(recursive(3))
