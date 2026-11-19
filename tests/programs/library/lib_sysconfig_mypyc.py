# sysconfig as mypyc and mypy read it (mypyc/common.py, mypy/pyinfo.py of mypy 2.4.1): the size
# of size_t, whether the build is free-threaded, and the directories to leave out of sys.path.
import os
import sys
import sysconfig
from typing import Final

# Size of size_t, if configured.
SIZEOF_SIZE_T_SYSCONFIG: Final = sysconfig.get_config_var("SIZEOF_SIZE_T")

SIZEOF_SIZE_T: Final = (
    int(SIZEOF_SIZE_T_SYSCONFIG)
    if SIZEOF_SIZE_T_SYSCONFIG is not None
    else (sys.maxsize + 1).bit_length() // 8
)

IS_32_BIT_PLATFORM: Final = int(SIZEOF_SIZE_T) == 4

# Are we running on a free-threaded build (GIL disabled)? This implies that
# we are on Python 3.13 or later.
IS_FREE_THREADED: Final = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))

print(SIZEOF_SIZE_T, IS_32_BIT_PLATFORM, IS_FREE_THREADED)


def getsitepackages() -> list[str]:
    return [sysconfig.get_paths()["purelib"]]


def getsyspath_excludes() -> list[str]:
    stdlib = sysconfig.get_path("stdlib")
    stdlib_ext = os.path.join(stdlib, "lib-dynload")
    return [stdlib, stdlib_ext]


sites = getsitepackages()
print(len(sites), os.path.isabs(sites[0]), os.path.basename(sites[0]))
excludes = getsyspath_excludes()
print(os.path.isdir(excludes[0]), os.path.basename(excludes[1]), os.path.dirname(excludes[1]) == excludes[0])
