""" This module tries to retrieve as much platform-identifying data as
    possible. It makes this information available via function APIs.

"""

# Pystachy's subset implementation of CPython 3.13.16's Lib/platform.py
# (lib/compatibility.md#platform). CPython's module asks os.uname(), sys.version, the Python
# executable's file and commands it runs. Here uname() reads the system's uname(2) through a
# private builtin, and the Python functions answer for Pystachy: its implementation name, and
# the version of the Python language it compiles (sys.version_info). The functions that
# describe the CPython build or run commands (platform(), processor(), architecture(),
# libc_ver(), python_build(), python_compiler() and the like) are not here.
import sys
from typing import NamedTuple

__all__ = ["uname", "uname_result", "system", "node", "release", "version", "machine",
           "python_implementation", "python_version", "python_version_tuple"]


class uname_result(NamedTuple):
    """
    A uname_result that's largely compatible with a
    simple namedtuple except that 'processor' is
    resolved late and cached to avoid calling "uname"
    except when needed.
    """
    # Pystachy port: a NamedTuple of CPython's five fields, without the processor that its
    # class adds as a sixth item (which CPython reads from the command uname -p)
    system: str
    node: str
    release: str
    version: str
    machine: str


_uname_cache: list[uname_result] = []


def uname() -> uname_result:
    """ Fairly portable uname interface. Returns a tuple
        of strings (system, node, release, version, machine, processor)
        identifying the underlying platform.

        Note that unlike the os.uname function this also returns
        possible processor information as an additional tuple entry.

        Entries which cannot be determined are set to ''.

    """
    # Pystachy port: the fields of the system's uname(2), as CPython's os.uname() gives them,
    # each '' where it is "unknown", as in CPython
    if not _uname_cache:
        _uname_cache.append(uname_result(_unknown_as_blank(__pys_uname(0)), _unknown_as_blank(__pys_uname(1)),
                                         _unknown_as_blank(__pys_uname(2)), _unknown_as_blank(__pys_uname(3)),
                                         _unknown_as_blank(__pys_uname(4))))
    return _uname_cache[0]


def _unknown_as_blank(val: str) -> str:
    return '' if val == 'unknown' else val


def system() -> str:
    """ Returns the system/OS name, e.g. 'Linux', 'Windows' or 'Java'.

        An empty string is returned if the value cannot be determined.

    """
    return uname().system


def node() -> str:
    """ Returns the computer's network name (which may not be fully
        qualified)

        An empty string is returned if the value cannot be determined.

    """
    return uname().node


def release() -> str:
    """ Returns the system's release, e.g. '2.2.0' or 'NT'

        An empty string is returned if the value cannot be determined.

    """
    return uname().release


def version() -> str:
    """ Returns the system's release version, e.g. '#3 on degas'

        An empty string is returned if the value cannot be determined.

    """
    return uname().version


def machine() -> str:
    """ Returns the machine type, e.g. 'i386'

        An empty string is returned if the value cannot be determined.

    """
    return uname().machine


def python_implementation() -> str:
    """ Returns a string identifying the Python implementation.

        Currently, the following implementations are identified:
          'CPython' (C implementation of Python),
          'Jython' (Java implementation of Python),
          'PyPy' (Python implementation of Python).

    """
    # Pystachy port: this implementation's name, sys.implementation.name capitalized
    return 'Pystachy'


def python_version() -> str:
    """ Returns the Python version as string 'major.minor.patchlevel'

        Note that unlike the Python sys.version, the returned value
        will always include the patchlevel (it defaults to 0).

    """
    # Pystachy port: of sys.version_info (CPython parses sys.version)
    return '%d.%d.%d' % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def python_version_tuple() -> tuple[str, str, str]:
    """ Returns the Python version as tuple (major, minor, patchlevel)
        of strings.

        Note that unlike the Python sys.version, the returned value
        will always include the patchlevel (it defaults to 0).

    """
    return (str(sys.version_info.major), str(sys.version_info.minor), str(sys.version_info.micro))
