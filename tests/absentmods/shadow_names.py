# Binds the name ModuleNotFoundError, for a module that imports all of its names.
def ModuleNotFoundError(s: str) -> ValueError:
    return ValueError(s)
