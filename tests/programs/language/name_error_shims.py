# A try whose body first reads a name that nothing but the try binds and that no builtin of
# CPython 3.13 is (Python 2's basestring, unicode, xrange, long; Windows' WindowsError), with a
# handler that catches NameError (by name, in a tuple, as Exception or BaseException, or bare), is
# decided at compile time, as CPython decides it where the module runs (#252): the handler
# runs, the rest of the try and its else block do not; also a def in the handler, and in an
# imported module (tests/mods/py2compat.py), also one whose handler raises ImportError, in an
# optional import (tests/mods/py2only.py). A try that only reads builtins (_IncompleteInputError
# too) or assigns them runs its body and else block, not its handlers
from mods.py2compat import NAMES, StrType, encoding

try:
    from mods.py2only import VERSION
except ImportError:
    VERSION = 3

try:
    string_types = basestring  # noqa: F821
except NameError:
    string_types = str

try:
    unicode  # noqa: F821
except NameError:
    unicode = str

try:
    absolute = xrange  # noqa: F821
    print("never")
except ImportError:
    print("never")
except (TypeError, NameError):
    absolute = abs
else:
    print("never")

try:
    long  # noqa: F821
except Exception:
    def as_int(s: str) -> int:
        return int(s)

try:
    integer_types = (int, long)  # noqa: F821
except BaseException:
    integer_types = (int,)

try:
    input_ = raw_input  # noqa: F821
except:  # noqa: E722
    input_ = "input"

print(string_types("x"), unicode(1.5), absolute(-3), as_int("42"), len(integer_types), input_)
print(NAMES, StrType(7) + "!", encoding(), encoding(False))
print(string_types("é") + unicode("!"))

try:
    text_type = str
except NameError:
    text_type = None
else:
    print("str is a builtin:", text_type(VERSION))

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError

try:
    _IncompleteInputError  # noqa: F821
except NameError:
    print("never")
else:
    print("_IncompleteInputError is a builtin")

try:
    open("/nonexistent/name_error_shims")
except FileNotFoundError:
    print("FileNotFoundError")
