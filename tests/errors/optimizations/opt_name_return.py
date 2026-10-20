# error: returning str | None from a function declared to return None
def get() -> str | None:
    return "a"


def f() -> None:
    return get()


print(f())
