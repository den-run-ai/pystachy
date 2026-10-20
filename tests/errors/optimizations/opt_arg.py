# error: argument 1 of shout() may be None (str | None); test it with 'is not None' first
def shout(s: str) -> str:
    return s.upper()


def greet(name: str | None) -> str:
    return shout(name)


print(greet("a"))
