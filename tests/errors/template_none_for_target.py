# error: 'v' is None here, and binding it as a for loop's target is not supported
def last(xs, v=None):
    for v in xs:
        pass
    return v


e: list[str] = []
print(last(e))
