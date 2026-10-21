# A try that reads a name is decided at compile time only where nothing but the try binds the
# name (tests/programs/language/name_error_shims.py). Where something else may have bound it, it runs as CPython
# runs it: a function's global statement, also of a def under a compile-time if or in an
# optional import, a statement of the module after the try, or another module through the
# module, in a circular import (tests/mods/shim_a.py; tests/mods/shim_c.py, whose try binds the
# name itself)
import os
import sys

import mods.shim_a
import mods.shim_c

if os.name == "posix":
    def setup() -> None:
        global foo
        foo = 1

if sys.version_info >= (3,):
    def setup_version() -> None:
        global bar
        bar = 2

try:
    import os.path

    def setup_optional() -> None:
        global baz
        baz = 3
except ImportError:
    pass

setup()
setup_version()
try:
    x = foo
except NameError:
    x = 0
try:
    y = bar
except NameError:
    y = 0
try:
    z = baz
except NameError:
    z = 0
try:
    w = later
except NameError:
    w = -1
later = 4
print(x, y, z, w, later, mods.shim_a.seen, mods.shim_a.flag, mods.shim_c.seen, mods.shim_c.unicode(5))
setup_optional()
try:
    z = baz
except NameError:
    z = 0
print(z)
