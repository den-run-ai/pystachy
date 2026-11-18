# An optional import in a function keeps its except clause for the statements after its imports
# too (#1504), whose handler may return; a closure's call may raise the subclass.
class Missing(ImportError):
    pass


def need(n: int) -> int:
    if n < 0:
        raise Missing(f"negative {n}")
    return n * 2


def compute(n: int) -> int:
    try:
        import json

        v = need(n)
    except ImportError:
        return -1
    return v


def outer(n: int) -> str:
    def inner() -> int:
        return need(n)

    try:
        import json

        r = json.dumps(inner())
    except ImportError as e:
        r = "fallback " + str(e)
    return r


print(compute(2), compute(-3))
print(outer(4), outer(-5))
