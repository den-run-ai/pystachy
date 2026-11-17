"""Access to Python's configuration information."""

# Pystachy's subset implementation of CPython 3.13.16's Lib/sysconfig/__init__.py
# (lib/compatibility.md#sysconfig). CPython's module reports the installation that runs the
# program: the variables of the Makefile and pyconfig.h it was built with, and the directories
# its installer writes. Here it answers for Pystachy. The variables are the ones CPython
# computes as it starts, for the Pystachy home (sys.prefix), with the few of a build that are
# true of every target; any other reads as None, as a variable CPython's build does not
# define. The one install scheme is the layout of that home, whose stdlib is the lib/ beside
# the compiler. The functions that read CPython's build files (get_makefile_filename(),
# get_config_h_filename(), parse_config_h()) and get_platform(), which needs os.uname(), are
# not here.
import os
import sys

__all__ = [
    'get_config_var',
    'get_config_vars',
    'get_path',
    'get_path_names',
    'get_paths',
    'get_python_version',
    'get_scheme_names',
]

# Pystachy port: the one scheme, of the Pystachy home. It has CPython's names, as its default
# scheme on POSIX, which a distributor changes to its layout: the standard library is lib/,
# without CPython's directory of the implementation and version. Nothing is installed in the
# other directories, and no import searches them (docs/language/modules.md): they are where
# the scheme puts them. There is no scheme of a home or user installation, or of a virtual
# environment.
_INSTALL_SCHEMES: dict[str, dict[str, str]] = {
    'posix_prefix': {
        'stdlib': '{installed_base}/{platlibdir}',
        'platstdlib': '{platbase}/{platlibdir}',
        'purelib': '{base}/lib/site-packages',
        'platlib': '{platbase}/{platlibdir}/site-packages',
        'include': '{installed_base}/include',
        'platinclude': '{installed_platbase}/include',
        'scripts': '{base}/bin',
        'data': '{base}',
        },
    }


def _get_implementation() -> str:
    return 'Pystachy'


_SCHEME_KEYS = ('stdlib', 'platstdlib', 'purelib', 'platlib', 'include',
                'scripts', 'data')

# Pystachy port: of sys.version_info, as there is no sys.version
_PY_VERSION = f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}'
_PY_VERSION_SHORT = f'{sys.version_info[0]}.{sys.version_info[1]}'
_PY_VERSION_SHORT_NO_DOT = f'{sys.version_info[0]}{sys.version_info[1]}'
_BASE_PREFIX = os.path.normpath(sys.base_prefix)
_BASE_EXEC_PREFIX = os.path.normpath(sys.base_exec_prefix)
# Pystachy port: empty until get_config_vars() fills it (a module global has one type here), and
# without CPython's lock: a program runs on one thread
_CONFIG_VARS: dict[str, int | str] = {}


def is_python_build() -> bool:
    # Pystachy port: never a CPython source tree, and without the deprecated check_home argument
    return False


def _split_vars(s: str) -> list[str]:
    # Pystachy port: the pieces of a scheme's path for _subst_vars(), which CPython formats with
    # str.format(**vars): the text before each {name}, then the name, and at last the rest
    parts: list[str] = []
    text = ''
    pos = 0
    while pos < len(s):
        c = s[pos]
        if c == '{' and s[pos + 1:pos + 2] == '{' or c == '}' and s[pos + 1:pos + 2] == '}':
            text += c
            pos += 2
        elif c == '{':
            end = s.find('}', pos)
            if end < 0:
                raise ValueError("expected '}' before end of string")
            parts.append(text)
            parts.append(s[pos + 1:end])
            text = ''
            pos = end + 1
        elif c == '}':
            raise ValueError("Single '}' encountered in format string")
        else:
            text += c
            pos += 1
    parts.append(text)
    return parts


def _subst_vars(s: str, local_vars: dict[str, str]) -> str:
    # Pystachy port: as CPython's, which formats the path with the variables or, when one is
    # missing, with the environment's alone
    parts = _split_vars(s)
    missing = False
    var = ''
    for i in range(1, len(parts), 2):
        if parts[i] not in local_vars:
            missing = True
            var = parts[i]
            break
    res = ''
    for i in range(0, len(parts) - 1, 2):
        name = parts[i + 1]
        if not missing:
            res += parts[i] + local_vars[name]
        elif name in os.environ:
            res += parts[i] + os.environ[name]
        else:
            raise AttributeError(f'{var!r}')
    return res + parts[-1]


def _expand_vars(scheme: str, vars: dict[str, str] | None) -> dict[str, str]:
    res: dict[str, str] = {}
    # Pystachy port: a dict of the variables as text, which leaves the caller's as it was; CPython
    # adds every configuration variable to the dict it is passed
    local_vars: dict[str, str] = {}
    if vars is not None:
        local_vars.update(vars)
    for name, config_value in get_config_vars().items():
        if name not in local_vars:
            local_vars[name] = str(config_value)

    for key, value in _INSTALL_SCHEMES[scheme].items():
        value = os.path.expanduser(value)
        res[key] = os.path.normpath(_subst_vars(value, local_vars))
    return res


def _get_preferred_schemes() -> dict[str, str]:
    return {
        'prefix': 'posix_prefix',
        'home': 'posix_home',
        'user': 'posix_user',
    }


def get_preferred_scheme(key: str) -> str:
    if key == 'prefix' and sys.prefix != sys.base_prefix:
        return 'venv'
    scheme = _get_preferred_schemes()[key]
    if scheme not in _INSTALL_SCHEMES:
        raise ValueError(
            f"{key!r} returned {scheme!r}, which is not a valid scheme "
            f"on this platform"
        )
    return scheme


def get_default_scheme() -> str:
    return get_preferred_scheme('prefix')


def get_scheme_names() -> tuple[str]:
    """Return a tuple containing the schemes names."""
    # Pystachy port: the one scheme's, a tuple of that length (CPython sorts its schemes' names)
    return ('posix_prefix',)


def get_path_names() -> tuple[str, str, str, str, str, str, str]:
    """Return a tuple containing the paths names."""
    return _SCHEME_KEYS


def get_paths(scheme: str = get_default_scheme(), vars: dict[str, str] | None = None,
              expand: bool = True) -> dict[str, str]:
    """Return a mapping containing an install scheme.

    ``scheme`` is the install scheme name. If not provided, it will
    return the default scheme for the current platform.
    """
    if expand:
        return _expand_vars(scheme, vars)
    else:
        return _INSTALL_SCHEMES[scheme]


def get_path(name: str, scheme: str = get_default_scheme(), vars: dict[str, str] | None = None,
             expand: bool = True) -> str:
    """Return a path corresponding to the scheme.

    ``scheme`` is the install scheme name.
    """
    return get_paths(scheme, vars, expand)[name]


def _init_config_vars() -> None:
    _PREFIX = os.path.normpath(sys.prefix)
    _EXEC_PREFIX = os.path.normpath(sys.exec_prefix)
    _CONFIG_VARS['prefix'] = _PREFIX
    _CONFIG_VARS['exec_prefix'] = _EXEC_PREFIX
    _CONFIG_VARS['py_version'] = _PY_VERSION
    _CONFIG_VARS['py_version_short'] = _PY_VERSION_SHORT
    _CONFIG_VARS['py_version_nodot'] = _PY_VERSION_SHORT_NO_DOT
    _CONFIG_VARS['installed_base'] = _BASE_PREFIX
    _CONFIG_VARS['base'] = _PREFIX
    _CONFIG_VARS['installed_platbase'] = _BASE_EXEC_PREFIX
    _CONFIG_VARS['platbase'] = _EXEC_PREFIX
    # Pystachy port: the name of lib/, and no ABI flags (there is no sys.platlibdir or
    # sys.abiflags); no projectbase, userbase or srcdir, which are of CPython's executable, user
    # site directory and Makefile
    _CONFIG_VARS['platlibdir'] = 'lib'
    _CONFIG_VARS['implementation'] = _get_implementation()
    _CONFIG_VARS['implementation_lower'] = _get_implementation().lower()
    _CONFIG_VARS['abiflags'] = ''
    _CONFIG_VARS['py_version_nodot_plat'] = ''

    # Pystachy port: in place of the variables of CPython's Makefile and pyconfig.h, the ones
    # that are true of every Pystachy target: the size of a pointer and of size_t, and a
    # runtime that is not free-threaded
    pointer_size = (sys.maxsize.bit_length() + 1) // 8
    _CONFIG_VARS['SIZEOF_SIZE_T'] = pointer_size
    _CONFIG_VARS['SIZEOF_VOID_P'] = pointer_size
    _CONFIG_VARS['Py_GIL_DISABLED'] = 0

    _CONFIG_VARS['abi_thread'] = 't' if _CONFIG_VARS.get('Py_GIL_DISABLED') else ''


def get_config_vars() -> dict[str, int | str]:
    """With no arguments, return a dictionary of all configuration
    variables relevant for the current platform.

    On Unix, this means every variable defined in Python's installed Makefile;
    On Windows it's a much smaller set.

    With arguments, return a list of values that result from looking up
    each argument in the configuration variable dictionary.
    """
    # Pystachy port: without arguments only, as a function has one return type here
    if len(_CONFIG_VARS) == 0:
        _init_config_vars()
    return _CONFIG_VARS


def get_config_var(name: str) -> int | str | None:
    """Return the value of a single variable using the dictionary returned by
    'get_config_vars()'.

    Equivalent to get_config_vars().get(name)
    """
    return get_config_vars().get(name)


def get_python_version() -> str:
    return _PY_VERSION_SHORT
