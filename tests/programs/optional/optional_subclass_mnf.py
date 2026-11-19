# The except clauses kept for the statements after an optional import's imports catch what
# CPython's do (#1504): a subclass of ModuleNotFoundError reaches except ModuleNotFoundError, but
# a subclass of ImportError alone passes it by, to a handler further out.
class NotFound(ModuleNotFoundError):
    pass


class Missing(ImportError):
    pass


def need(kind: int) -> int:
    if kind == 1:
        raise NotFound("not found")
    if kind == 2:
        raise Missing("missing")
    return kind


try:
    import json

    a = need(1)
except ModuleNotFoundError as e:
    a = -1
    print("ModuleNotFoundError", type(e).__name__, e)
print(a)


def load(kind: int) -> int:
    try:
        import json

        v = need(kind)
    except ModuleNotFoundError:
        v = -1
    return v


for kind in [0, 1, 2]:
    try:
        print(kind, load(kind))
    except ImportError as e:
        print(kind, "escaped", type(e).__name__, e)

try:
    import json

    b = need(2)
except (ModuleNotFoundError, ImportError) as e:
    b = -2
    print("tuple", type(e).__name__, isinstance(e, ModuleNotFoundError))
print(b)
