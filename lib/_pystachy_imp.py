"""Import capability queries and a recursive lock for one-thread Pystachy programs.

This prototype does not load modules at runtime. Ordinary imports are resolved
while compiling; compiler builtin namespaces are not a runtime builtin registry.
See docs/prototypes/imp.md for the supported surface and deliberate differences.
"""

_lock_depth = 0


def acquire_lock() -> None:
    global _lock_depth
    _lock_depth += 1


def release_lock() -> None:
    global _lock_depth
    if _lock_depth == 0:
        raise RuntimeError("not holding the import lock")
    _lock_depth -= 1


def lock_held() -> bool:
    return _lock_depth != 0


def extension_suffixes() -> list[str]:
    # ffi.extern loads C symbols; it is not a Python extension-module loader.
    return []


def _frozen_module_names() -> list[str]:
    return []


def is_frozen(name: str, /) -> bool:
    return False


def find_frozen(name: str, /, *, withdata: bool = False) -> None:
    return None


def is_frozen_package(name: str, /) -> bool:
    # CPython raises for an unknown name, rather than returning False.
    raise ImportError(f"No such frozen object named {name!r}")


def get_frozen_object(name: str, data: bytes | None = None, /) -> None:
    if data is not None:
        raise NotImplementedError("_imp.get_frozen_object() cannot decode code objects: Pystachy has no Python bytecode interpreter")
    raise ImportError(f"No such frozen object named {name!r}")


def init_frozen(name: str, /) -> None:
    # CPython returns None if no such frozen module exists; no initialization occurs.
    return None


def is_builtin(name: str, /) -> int:
    raise NotImplementedError("_imp.is_builtin() is not supported: Pystachy's compiler builtin namespaces have no runtime module registry")


def create_builtin(spec, /) -> None:
    raise NotImplementedError("_imp.create_builtin() is not supported: Pystachy resolves imports while compiling")


def exec_builtin(mod, /) -> None:
    raise NotImplementedError("_imp.exec_builtin() is not supported: Pystachy resolves imports while compiling")


def create_dynamic(spec, file=None, /) -> None:
    raise NotImplementedError("_imp.create_dynamic() is not supported: Pystachy has no Python extension-module loader")


def exec_dynamic(mod, /) -> None:
    raise NotImplementedError("_imp.exec_dynamic() is not supported: Pystachy has no Python extension-module loader")
