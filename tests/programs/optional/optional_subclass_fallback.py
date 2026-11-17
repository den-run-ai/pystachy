# Where the program does not compile with an optional import's except clauses kept for the
# statements after its imports (#1504), it compiles as before: here the handler's None would make
# n an int | None, which the annotated assignment after the try does not take. The subclass is
# never raised, so CPython's output is the same; tests/deviations/optional_subclass_escapes.py
# raises it.
class Missing(ImportError):
    pass


def need(flag: bool) -> int:
    if flag:
        raise Missing("unavailable")
    return 1


try:
    import json

    n = need(False)
except ImportError:
    n = None
count: int = n
print(count + 1, json.dumps([count]))
