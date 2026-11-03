# error: copy.copy() of a Buffer object is not supported: its class derives from StringIO, a library's class, which defines no __copy__ or __deepcopy__ for it
# CPython copies a StringIO's buffer through its __getstate__ (printing a)
import copy
import io


class Buffer(io.StringIO):
    pass


b = Buffer()
b.write("a")
print(copy.copy(b).getvalue())
