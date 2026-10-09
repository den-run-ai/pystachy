# OSError(errno, strerror) with an errno that may be None: an int makes the subclass it names
# (2 FileNotFoundError, 13 PermissionError), None a plain OSError, as CPython's does
def go(code: int | None) -> None:
    try:
        raise OSError(code, "nope")
    except FileNotFoundError as e:
        print("FNF", repr(e), e)
    except PermissionError as e:
        print("PE", repr(e), e)
    except OSError as e:
        print("OSError", repr(e), e)


def make(code: int | None, name: str | None) -> OSError:
    return OSError(code, "why", name)


for c in [2, 13, None, 99]:
    go(c)
for c in [2, None]:
    e = make(c, "f.txt" if c is not None else None)
    print(type(e).__name__, repr(e), str(e))
