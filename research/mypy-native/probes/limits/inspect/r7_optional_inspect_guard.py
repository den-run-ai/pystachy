# an optional import of inspect whose guarded code uses a name the subset lacks, in a function
# that is called: before lib/inspect.py the import was missing and the fallback ran; now the
# module is there, and the guarded call is a compile-time error
try:
    import inspect
except ImportError:
    inspect = None


def area(w: int, h: int) -> int:
    return w * h


def arity(f) -> int:
    if inspect is not None:
        return len(inspect.signature(f).parameters)
    return 2


print(arity(area))
