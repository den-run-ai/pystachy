# An optional import whose handler binds a builtin's name is decided as before (#1504): where
# the handler has not run, a read of that name finds the builtin, as in CPython.
class Missing(ImportError):
    pass


def need(flag: bool) -> int:
    if flag:
        raise Missing("unavailable")
    return 1


def mylen(s: str) -> int:
    return -1


try:
    import json

    n = need(False)
except ImportError:
    len = mylen
    n = 0
print(n, len("abc"), json.dumps([n]))
