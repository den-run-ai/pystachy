# error: (compiling show(str | None) for the call at
def show(v):
    return v.nope


def get() -> str | None:
    return None


print(show(get()))
