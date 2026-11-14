"""
Read resources contained within a package.
"""
# Pystachy's subset implementation of CPython 3.13.16's Lib/importlib/resources
# (lib/compatibility.md#importlib): files() of a module's name, as_file() and the functions
# that open, read or test one resource of a package. CPython imports the module that files()
# names and asks its loader for the resources. Pystachy resolves imports while it compiles a
# program, so files() looks the name up among the modules the program imports (the compiler's
# primitive __pys_module_files(), a table of their files) and returns the directory of the
# module's file, a pathlib.Path, as CPython does for a module that it loads from a file. The
# table holds the paths the compiler read: an executable built from the program keeps them.
import contextlib
from pathlib import Path, UnsupportedOperation

__all__ = [
    'as_file',
    'files',
    'is_resource',
    'open_binary',
    'open_text',
    'path',
    'read_binary',
    'read_text',
]


_files: dict[str, str] = {}  # the compiler's table of the program's module files, once read


def _module_file(anchor: str) -> str:
    # the file of the program's module anchor: what CPython's import_module(anchor) loads, with
    # its errors for a name that the program has no module of
    if anchor == '':
        raise ValueError('Empty module name')
    if anchor.startswith('.'):
        raise TypeError("the 'package' argument is required to perform a "
                        f"relative import for {anchor!r}")
    if len(_files) == 0:
        _files.update(__pys_module_files())  # (never empty: it holds this module)
    table = _files
    name = ''
    for part in anchor.split('.'):
        parent = name
        name = part if name == '' else name + '.' + part
        if name not in table:
            # (CPython imports the parents first: the first missing one is the error)
            if parent != '' and table[parent] != '' and not table[parent].endswith('/__init__.py'):
                raise ModuleNotFoundError(f'No module named {name!r}; {parent!r} is not a package')
            raise ModuleNotFoundError(f'No module named {name!r}')
    return table[anchor]


def files(anchor: str) -> Path:
    """
    Get a Traversable resource for an anchor.
    """
    file = _module_file(anchor)
    if file == '':
        raise NotImplementedError(f'importlib.resources.files() of the namespace package {anchor!r} '
                                  'is not supported: a package needs an __init__.py')
    return Path(file[: file.rfind('/')] or '/')


@contextlib.contextmanager
def as_file(path):
    """
    Given a Traversable object, return that object as a
    path on the local file system in a context manager.
    """
    # (a resource is a file of the file system here: the path itself, as CPython gives for one)
    yield path


def _get_resource(anchor: str, path_names: list[str]) -> Path:
    resource = files(anchor)
    for name in path_names:
        resource = resource / name
    return resource


def _get_encoding_arg(path_names: list[str], encoding: str | None) -> str:
    # For compatibility with versions where *encoding* was a positional
    # argument, it needs to be given explicitly when there are multiple
    # *path_names*.
    # This limitation can be removed in Python 3.15.
    if encoding is not None:
        return encoding
    if len(path_names) > 1:
        raise TypeError(
            "'encoding' argument required with multiple path names",
        )
    return 'utf-8'


def open_binary(anchor: str, *path_names: str):
    """Open for binary reading the *resource* within *package*."""
    return open(str(_get_resource(anchor, list(path_names))), 'rb')


def open_text(anchor: str, *path_names: str, encoding: str | None = None, errors: str = 'strict'):
    """Open for text reading the *resource* within *package*."""
    encoding = _get_encoding_arg(list(path_names), encoding)
    resource = _get_resource(anchor, list(path_names))
    if errors != 'strict':
        # (as Path.open(): Pystachy's files have no error handlers)
        raise UnsupportedOperation("importlib.resources.open_text() and read_text() with errors "
                                   "other than 'strict' are not supported")
    return open(str(resource), 'r', encoding=encoding)


def read_binary(anchor: str, *path_names: str) -> bytes:
    """Read and return contents of *resource* within *package* as bytes."""
    with open_binary(anchor, *path_names) as f:
        return f.read()


def read_text(anchor: str, *path_names: str, encoding: str | None = None, errors: str = 'strict') -> str:
    """Read and return contents of *resource* within *package* as str."""
    with open_text(anchor, *path_names, encoding=encoding, errors=errors) as f:
        return f.read()


def path(anchor: str, *path_names: str):
    """Return the path to the *resource* as an actual file system path."""
    return as_file(_get_resource(anchor, list(path_names)))


def is_resource(anchor: str, *path_names: str) -> bool:
    """Return ``True`` if there is a resource named *name* in the package,

    Otherwise returns ``False``.
    """
    return _get_resource(anchor, list(path_names)).is_file()
