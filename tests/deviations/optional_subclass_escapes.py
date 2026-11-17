# Documented deviation (#1504): where the program does not compile with an optional import's
# except clauses kept for the statements after its imports (here the handler's None would make n
# an int | None, which the annotated assignment after the try does not take), it compiles as
# before, and a subclass of ImportError that those statements raise ends the program. CPython
# runs the handler and prints "fallback".
class Missing(ImportError):
    pass


def need(flag: bool) -> int:
    if flag:
        raise Missing("unavailable")
    return 1


try:
    import json

    n = need(True)
except ImportError:
    n = None
count: int = n
print("fallback" if count is None else json.dumps([count]))
