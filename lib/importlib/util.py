"""Utility code for constructing importers, etc."""
# Pystachy's subset of CPython 3.13.16's Lib/importlib/util.py (lib/compatibility.md#importlib):
# resolve_name(), with the code of CPython's function and of _bootstrap._resolve_name(), which
# it calls. The functions that find, load or cache modules are not here: Pystachy resolves
# imports while it compiles a program.


def _resolve_name(name: str, package: str, level: int) -> str:
    """Resolve a relative module name to an absolute one."""
    bits = package.rsplit('.', level - 1)
    if len(bits) < level:
        raise ImportError('attempted relative import beyond top-level package')
    base = bits[0]
    return f'{base}.{name}' if name else base


def resolve_name(name: str, package: str | None) -> str:
    """Resolve a relative module name to an absolute one."""
    if not name.startswith('.'):
        return name
    elif not package:
        raise ImportError(f'no package specified for {repr(name)} '
                          '(required for relative module names)')
    level = 0
    for character in name:
        if character != '.':
            break
        level += 1
    return _resolve_name(name[level:], package, level)
