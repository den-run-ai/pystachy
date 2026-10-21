# A template's parameter whose argument is None: len() of it (in a branch that runs only for
# other arguments) raises CPython's error where it runs


def size(xs, check):
    if check:
        return len(xs)
    return 0


print(size([1, 2], True), size(None, False))
print(size(None, True))
