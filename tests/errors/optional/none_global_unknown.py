# error: none_global_unknown.py:13: error: unsupported call len(None)
# A module global first None, read where its type is needed, which only a template
# function (nothing calls it) gives another value.
last = None


def keep(v) -> None:
    global last
    last = v


def size() -> int:
    return len(last)


print(size())
