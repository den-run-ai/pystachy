# C.__module__ = v of an exception class: from then on, C.__module__, type(e).__module__, repr(C)
# and an uncaught exception's line name v (here excmod, as the package assigns it); what was
# read before, and a subclass's, stay as they were; "__main__" shows the bare name. A __module__ in
# the class body is the class's from the start, as CPython's namespace gives it
import excmod


class Local(Exception):
    pass


class Named(ValueError):
    __module__ = "pkg"  # (CPython's class takes it from its namespace: what it shows)


def module_of_named() -> str:
    return Named.__module__


print(excmod.Boom.__module__, excmod.Worse.__module__, repr(excmod.Boom), str(excmod.Worse))
try:
    excmod.boom(0)
except excmod.Boom as e:
    print(type(e).__module__, type(e).__name__, repr(e), e)
try:
    excmod.boom(1)
except ValueError as e:
    print(type(e).__module__, type(e).__name__, isinstance(e, excmod.Boom))
print(Local.__module__)
Local.__module__ = "elsewhere.deep"
print(Local.__module__, repr(Local))
Local.__module__ = "__main__"
print(Local.__module__, repr(Local))
try:
    raise Named("n")
except Named as e:
    print(module_of_named(), type(e).__module__, repr(Named), repr(e))
Named.__module__ = "other"
print(module_of_named(), Named.__module__, repr(Named))
excmod.boom(0)
