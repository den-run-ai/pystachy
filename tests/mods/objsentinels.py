# a module's object() sentinel, which its importers read (tests/object_sentinel.py)
NOTHING = object()


def describe(value=NOTHING) -> str:
    if value is NOTHING:
        return "nothing given"
    return "something given"
