# __module__ and __qualname__ of exception classes, read through a class's name and through its
# class object: builtin classes', the main program's and those of a module of a package (mods.errs)
from mods.errs import Missing, StoreError


class Local(Exception):
    pass


def names(c: type[BaseException]) -> str:
    return f"{c.__module__} {c.__qualname__} {c.__name__}"


print(Local.__module__, Local.__qualname__)
print(Missing.__module__, Missing.__qualname__, StoreError.__module__)
print(KeyError.__module__, KeyError.__qualname__)
for c in [Local, Missing, StoreError, KeyError, OSError]:
    print(names(c))
try:
    raise Missing("k")
except Exception as e:
    print(names(type(e)))
