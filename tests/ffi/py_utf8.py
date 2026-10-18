# embedded CPython starts as python3 does: in the C or POSIX locale (tests/ffi/run.sh runs this one
# with LC_ALL, LC_CTYPE and LANG unset, and PYTHONCOERCECLOCALE=0) UTF-8 mode is on
from pyobj import import_module, of_str

sys = import_module("sys")
print("utf8 mode", sys.attr("flags").attr("utf8_mode"), sys.attr("getfilesystemencoding").call([]), sys.attr("stdout").attr("encoding"))
print("LC_CTYPE", import_module("os").attr("environ").attr("get").call([of_str("LC_CTYPE")]))
import_module("builtins").attr("print").call([of_str("héllo wörld")])
print("héllo again")
