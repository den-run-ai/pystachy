# A module's own __getattr__ (PEP 562), which CPython calls for a name the module lacks: Pystachy
# compiles it as any function and calls it for no name (tests/errors/imports/import_module_getattr*.py)
def __getattr__(name: str) -> int:
    return 7


def double(x: int) -> int:
    return 2 * x
