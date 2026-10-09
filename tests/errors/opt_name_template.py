# error: (compiling show(str | None) for the call at
def show(v):
    return isinstance(v, type(None))


def get() -> str | None:
    return None


print(show(get()))
