# An import in a function binds a name of that function only. A from-import of a module's
# variable rebinds a local as an assignment does (a parameter too, and on each pass of a loop),
# an optional import binds the name once, by the import or by its handler, and a template that
# is never compiled may bind a name both by an import and as a variable.
def limit() -> int:
    LIMIT = 10
    print("local", LIMIT)
    from mods.counter import LIMIT
    return LIMIT


def param(count: int) -> int:
    print("param", count)
    from mods.counter import count
    return count


def loop() -> list[int]:
    out: list[int] = []
    for i in range(2):
        from mods.counter import LIMIT
        out.append(LIMIT)
        LIMIT = 10 + i
        out.append(LIMIT)
    return out


def fallback() -> float:
    try:
        from math import tau
    except ImportError:
        tau = 6.0
    return tau


def missing() -> bool:
    try:
        import no_such_module_here as nm
    except ImportError:
        nm = None
    return nm is None


def unused(v):
    sep = "x"
    from os import sep
    return sep


print(limit(), param(5), loop(), fallback(), missing())
