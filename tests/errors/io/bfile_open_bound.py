# error: open() of a binary mode is only supported by that name, with a literal mode, in a module that binds no other open
# (a parameter named open: the module's calls of open may be another function's)
def first(p: str) -> bytes:
    with open(p, "rb") as f:
        return f.read()


def other(open: int) -> int:
    return open + 1


print(other(1))
