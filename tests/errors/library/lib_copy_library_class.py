# error: copy.deepcopy() of a StringIO object is not supported: its class is a library's, which defines no __copy__ or __deepcopy__ for it
# CPython copies a StringIO's buffer through its __getstate__ (printing a)
import copy
import io

print(copy.deepcopy(io.StringIO("a")).getvalue())
