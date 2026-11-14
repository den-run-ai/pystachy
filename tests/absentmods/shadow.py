# A module that binds the name ModuleNotFoundError itself before an import of a missing module.
def ModuleNotFoundError(s: str) -> ValueError:
    return ValueError(s)


print("shadow: before the import")
import _pystachy_absent_c
print("shadow: not reached")
