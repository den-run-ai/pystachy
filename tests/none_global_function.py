# A module global first None, given a value by a function (global last): T | None, as a
# local's first other value types it, also where a read comes first.
last = None


def remember(v: str) -> None:
    global last
    last = v


print(last)
remember("a")
print(last, last is None)
remember("bc")
if last is not None:
    print(len(last))
