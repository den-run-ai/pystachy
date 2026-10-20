# error: cannot infer what recursive() returns: recursion already used None; annotate its return type
remaining = 1


def recursive():
    global remaining
    if remaining > 0:
        remaining -= 1
        recursive()
    return 1


print(recursive())
