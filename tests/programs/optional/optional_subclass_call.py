# Once an optional import's modules resolve, the statements after the imports still run with the
# except clauses, as in CPython (#1504): a subclass of ImportError that they raise through a call
# reaches the handler, and the else block runs only where nothing is raised.
class Missing(ImportError):
    pass


def need(flag: bool) -> str:
    if flag:
        raise Missing("optional backend unavailable")
    return "backend"


try:
    import json

    backend = need(True)
except ImportError:
    backend = "fallback"
print(backend, json.dumps([1]))

try:
    import json

    other = need(False)
except ImportError:
    other = "fallback"
else:
    other += " (else)"
print(other)

try:
    import json

    first = need(False)
    second = need(True)
except ImportError as e:
    second = f"caught {type(e).__name__}: {e}"
else:
    second = "else"
print(first, second)
