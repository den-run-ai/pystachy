# error: cannot infer the type of 'last' from None; annotate it (last: T | None = None)
last = None


def remember(v: str) -> None:
    global last
    last = v  # (only module code's values type a global)


remember("a")
print(last)
