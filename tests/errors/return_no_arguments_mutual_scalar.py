# error: cannot infer what first() returns: recursion already used None; annotate its return type
remaining = 1


def first():
    return second()


def second():
    global remaining
    if remaining > 0:
        remaining -= 1
        first()
    return 1


print(first())
