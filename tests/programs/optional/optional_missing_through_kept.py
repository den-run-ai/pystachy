# An optional import of a module that fails because a module it imports needs a missing one,
# then an optional import whose statements after the imports raise a subclass of ImportError:
# each keeps its own record, so the first runs its handler and the second keeps its except
# clause (#1504), as CPython runs them.
class Missing(ImportError):
    pass


def need(flag: bool) -> str:
    if flag:
        raise Missing("optional backend unavailable")
    return "backend"


try:
    import absentmods.through
except ImportError:
    print("fallback: through")

try:
    import json

    backend = need(True)
except ImportError:
    backend = "fallback: subclass"
print(backend, json.dumps([1]))
