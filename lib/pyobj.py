"""Python objects for Pystachy code, through CPython's stable ABI (@ffi.extern). In a program,
CPython runs embedded (PYSTACHY_LIBPYTHON names its libpython); in an extension module (pystachy
ext) the host interpreter is used. tools/rt_cpython/pyobj.py is this module for CPython itself, and
a program may use only what both offer (__all__; an Object's fields are this module's own).

An Object holds a reference until close(), or until a collection finds the Object dropped (the
reference is then released by the next operation); a closed Object raises ValueError. A Python
exception becomes the nearest builtin exception class Pystachy has, with the same str();
SystemExit and KeyboardInterrupt stay what they are. Embedded, the program holds the GIL only
inside these calls, so Python threads run while compiled code does, and CPython is finalized
after the program ends (pyembed.c), as it is when it runs a script."""
import os
import sys
from ffi import extern, c_int, c_int64, c_ssize_t, c_void_p, c_buf, string_at, track, untrack, collected

__all__ = ["Object", "import_module", "of_int", "of_float", "of_str", "of_list"]


@extern("python")
def Py_IsInitialized() -> c_int: ...
@extern("python")
def Py_InitializeEx(sigs: c_int) -> None: ...
@extern("python")
def PyEval_SaveThread() -> c_void_p: ...
@extern("python")
def PyImport_ImportModule(name: str) -> c_void_p: ...
@extern("python")
def PyObject_GetAttrString(o: c_void_p, name: str) -> c_void_p: ...
@extern("python")
def Py_DecRef(o: c_void_p) -> None: ...
@extern("python")
def Py_IncRef(o: c_void_p) -> None: ...
@extern("python")
def PyLong_FromLongLong(v: c_int64) -> c_void_p: ...
@extern("python")
def PyLong_AsLongLong(o: c_void_p) -> c_int64: ...
@extern("python")
def PyFloat_FromDouble(x: float) -> c_void_p: ...
@extern("python")
def PyFloat_AsDouble(o: c_void_p) -> float: ...
@extern("python")
def PyUnicode_DecodeUTF8(s: c_buf, n: c_ssize_t, errors: str) -> c_void_p: ...
@extern("python")
def PyUnicode_AsEncodedString(o: c_void_p, encoding: str, errors: str) -> c_void_p: ...
@extern("python")
def PyBytes_Size(o: c_void_p) -> c_ssize_t: ...
@extern("python")
def PyBytes_AsString(o: c_void_p) -> c_void_p: ...
@extern("python")
def PyObject_Str(o: c_void_p) -> c_void_p: ...
@extern("python")
def PyObject_Repr(o: c_void_p) -> c_void_p: ...
@extern("python")
def PyTuple_New(n: c_ssize_t) -> c_void_p: ...
@extern("python")
def PyTuple_SetItem(t: c_void_p, i: c_ssize_t, o: c_void_p) -> c_int: ...
@extern("python")
def PyTuple_GetItem(t: c_void_p, i: c_ssize_t) -> c_void_p: ...
@extern("python")
def PyTuple_Size(t: c_void_p) -> c_ssize_t: ...
@extern("python")
def PyList_New(n: c_ssize_t) -> c_void_p: ...
@extern("python")
def PyList_Append(lst: c_void_p, o: c_void_p) -> c_int: ...
@extern("python")
def PyObject_Call(f: c_void_p, args: c_void_p, kwargs: c_void_p) -> c_void_p: ...
@extern("python")
def PyObject_GetItem(o: c_void_p, k: c_void_p) -> c_void_p: ...
@extern("python")
def PyObject_Length(o: c_void_p) -> c_ssize_t: ...
@extern("python")
def PyObject_IsTrue(o: c_void_p) -> c_int: ...
@extern("python")
def PyErr_Occurred() -> c_void_p: ...
@extern("python")
def PyErr_GetRaisedException() -> c_void_p: ...
@extern("python")
def PyObject_Type(o: c_void_p) -> c_void_p: ...
@extern("python")
def PySys_GetObject(name: str) -> c_void_p: ...
@extern("python")
def PySys_SetObject(name: str, o: c_void_p) -> c_int: ...
# pyembed.c: CPython set up as its own main sets it up, the GIL with the two runtimes' output in order,
# and a Python object's size
@extern("")
def pye_preinit() -> None: ...
@extern("")
def pye_init() -> c_int: ...
@extern("")
def pye_enter() -> c_int: ...
@extern("")
def pye_leave(g: c_int) -> None: ...
@extern("")
def pye_sizeof(o: c_void_p) -> c_int64: ...
@extern("")
def pye_flush() -> None: ...
@extern("")
def pye_exit(e: c_void_p) -> None: ...


_BUILTIN = ["KeyError", "IndexError", "ZeroDivisionError", "OverflowError", "ValueError", "TypeError",
            "AttributeError", "ModuleNotFoundError", "ImportError", "NotImplementedError", "RecursionError",
            "RuntimeError", "FileNotFoundError", "OSError", "StopIteration", "AssertionError", "LookupError",
            "ArithmeticError", "EOFError", "KeyboardInterrupt", "SystemExit", "GeneratorExit", "Exception",
            "BaseException"]


def _text(o: int, alt: str) -> str:
    # a Python str (a new reference, which this releases) as Pystachy's UTF-8 str; when o is NULL or
    # cannot be encoded, alt (the error dropped)
    if o == 0:
        Py_DecRef(PyErr_GetRaisedException())
        return alt
    b = PyUnicode_AsEncodedString(o, "utf-8", "surrogatepass")
    Py_DecRef(o)
    if b == 0:
        Py_DecRef(PyErr_GetRaisedException())
        return alt
    s = string_at(PyBytes_AsString(b), PyBytes_Size(b))
    Py_DecRef(b)
    return s


def _raise() -> None:
    # the Python exception just raised, as the first builtin class in its type's __mro__ that
    # Pystachy has, with its str() (if str() raises, what it raised instead, once); a SystemExit
    # is raised as it is (pye_exit)
    e = PyErr_GetRaisedException()
    if e == 0:
        raise RuntimeError("error return without exception set")
    k = "Exception"
    m = ""
    again = True
    while True:
        t = PyObject_Type(e)
        mro = PyObject_GetAttrString(t, "__mro__")
        Py_DecRef(t)
        k = "Exception"
        for i in range(PyTuple_Size(mro) if mro != 0 else 0):
            n = _text(PyObject_GetAttrString(PyTuple_GetItem(mro, i), "__name__"), "")  # (borrowed item)
            if n in _BUILTIN:
                k = n
                break
        Py_DecRef(mro)
        if k == "SystemExit":
            # the status its code gives CPython's own exit (one beyond 64 bits too), its str() and its repr()
            pye_exit(e)  # (which returns only if str(e) or repr(e) raises: then it is raised as any other)
        s = PyObject_Str(e)
        if s != 0 or not again:
            m = _text(s, "<exception str() failed>")
            Py_DecRef(e)
            break
        Py_DecRef(e)
        e = PyErr_GetRaisedException()  # (str(e) raised: that is raised instead, as the twin's str(e) raises it)
        again = False
        if e == 0:
            m = "<exception str() failed>"
            break
    if k == "KeyboardInterrupt":
        raise KeyboardInterrupt(m)
    if k == "StopIteration":
        raise StopIteration(m)
    if k == "KeyError":
        raise KeyError(m)
    if k == "IndexError":
        raise IndexError(m)
    if k == "ZeroDivisionError":
        raise ZeroDivisionError(m)
    if k == "OverflowError":
        raise OverflowError(m)
    if k == "ValueError":
        raise ValueError(m)
    if k == "TypeError":
        raise TypeError(m)
    if k == "AttributeError":
        raise AttributeError(m)
    if k == "ModuleNotFoundError":
        raise ModuleNotFoundError(m)
    if k == "ImportError":
        raise ImportError(m)
    if k == "NotImplementedError":
        raise NotImplementedError(m)
    if k == "RuntimeError" or k == "RecursionError":
        raise RuntimeError(m)
    if k == "FileNotFoundError":
        raise FileNotFoundError(m)
    if k == "OSError":
        raise OSError(m)
    if k == "AssertionError":
        raise AssertionError(m)
    if k == "LookupError":
        raise LookupError(m)
    if k == "ArithmeticError":
        raise ArithmeticError(m)
    if k == "EOFError":
        raise EOFError(m)
    if k == "SystemExit":
        raise SystemExit(m)
    if k == "GeneratorExit":
        raise GeneratorExit(m)
    if k == "BaseException":
        raise BaseException(m)
    raise Exception(m)


def _enter() -> int:
    # attach to CPython (the GIL, with Pystachy's pending output written first: pyembed.c) for one
    # operation, after releasing the references of Objects that collections found dropped: here,
    # not inside a collection (Py_DecRef runs Python code). That is safe at any depth (Python code
    # calling back into an extension module), as each operation owns the references it uses (_own)
    g = pye_enter()
    v = collected()
    while v != 0:
        Py_DecRef(v)
        v = collected()
    return g


def _leave(g: int) -> None:
    pye_leave(g)


def _own(p: int) -> int:
    # an operation's own reference to the object an Object holds (released when the operation ends)
    if p == 0:
        raise ValueError("operation on a closed Python object")
    Py_IncRef(p)
    return p


def _ref(p: int, n: int) -> "Object":
    # a new reference (NULL: the error raised) as an Object; n: what it holds (-1: sys.getsizeof)
    if p == 0:
        _raise()
    return Object(p, pye_sizeof(p) if n < 0 else n)


class Object:
    # made by this module only (the twin's Object is another class); every operation owns the
    # references it uses, so a release that runs meanwhile cannot free them
    def __init__(self, p: int, n: int) -> None:
        self._p = p  # a strong reference, a PyObject *; 0 once closed
        self._t: int = track(self, p, n)  # (released when a collection finds this Object dropped)

    def close(self) -> None:
        g = _enter()
        try:
            p = self._p
            if p != 0:
                self._p = 0
                untrack(self._t)
                Py_DecRef(p)
        finally:
            _leave(g)

    def attr(self, name: str) -> "Object":
        g = _enter()
        p = 0
        try:
            p = _own(self._p)
            return _ref(PyObject_GetAttrString(p, name), -1)
        finally:
            Py_DecRef(p)
            _leave(g)

    def call(self, args: list["Object"]) -> "Object":
        g = _enter()
        p = 0
        t = 0
        try:
            p = _own(self._p)
            t = PyTuple_New(len(args))
            if t == 0:
                _raise()
            for i in range(len(args)):
                PyTuple_SetItem(t, i, _own(args[i]._p))  # (steals the reference _own took)
            pye_flush()  # (what was printed reaches stdout's file before the call, as the twin flushes sys.stdout)
            return _ref(PyObject_Call(p, t, 0), -1)
        finally:
            Py_DecRef(t)
            Py_DecRef(p)
            _leave(g)

    def __getitem__(self, k: "Object") -> "Object":
        g = _enter()
        p = 0
        q = 0
        try:
            p = _own(self._p)
            q = _own(k._p)
            return _ref(PyObject_GetItem(p, q), -1)
        finally:
            Py_DecRef(q)
            Py_DecRef(p)
            _leave(g)

    def __len__(self) -> int:
        g = _enter()
        p = 0
        try:
            p = _own(self._p)
            n = PyObject_Length(p)
            if n < 0:
                _raise()
            return n
        finally:
            Py_DecRef(p)
            _leave(g)

    def __bool__(self) -> bool:
        g = _enter()
        p = 0
        try:
            p = _own(self._p)
            r = PyObject_IsTrue(p)
            if r < 0:
                _raise()
            return r == 1
        finally:
            Py_DecRef(p)
            _leave(g)

    def to_int(self) -> int:
        g = _enter()
        p = 0
        try:
            p = _own(self._p)
            v = PyLong_AsLongLong(p)
            if v == -1 and PyErr_Occurred() != 0:
                _raise()
            return v
        finally:
            Py_DecRef(p)
            _leave(g)

    def to_float(self) -> float:
        g = _enter()
        p = 0
        try:
            p = _own(self._p)
            v = PyFloat_AsDouble(p)
            if v == -1.0 and PyErr_Occurred() != 0:
                _raise()
            return v
        finally:
            Py_DecRef(p)
            _leave(g)

    def __str__(self) -> str:
        g = _enter()
        p = 0
        try:
            p = _own(self._p)
            r = PyObject_Str(p)
            if r == 0:
                _raise()
            return _text(r, "")
        finally:
            Py_DecRef(p)
            _leave(g)

    def __repr__(self) -> str:
        g = _enter()
        p = 0
        try:
            p = _own(self._p)
            r = PyObject_Repr(p)
            if r == 0:
                _raise()
            return _text(r, "")
        finally:
            Py_DecRef(p)
            _leave(g)


def import_module(name: str) -> Object:
    g = _enter()
    try:
        return _ref(PyImport_ImportModule(name), -1)
    finally:
        _leave(g)


def of_int(v: int) -> Object:
    g = _enter()
    try:
        return _ref(PyLong_FromLongLong(v), 0)
    finally:
        _leave(g)


def of_float(x: float) -> Object:
    g = _enter()
    try:
        return _ref(PyFloat_FromDouble(x), 0)
    finally:
        _leave(g)


def of_str(s: str) -> Object:
    g = _enter()
    try:
        return _ref(PyUnicode_DecodeUTF8(s, len(s), "surrogatepass"), len(s))
    finally:
        _leave(g)


def of_list(xs: list[Object]) -> Object:
    g = _enter()
    r = 0
    try:
        r = PyList_New(0)
        if r == 0:
            _raise()
        for x in xs:
            q = _own(x._p)
            e = PyList_Append(r, q)
            Py_DecRef(q)
            if e < 0:
                _raise()
        o = _ref(r, -1)
        r = 0
        return o
    finally:
        Py_DecRef(r)
        _leave(g)


def _check() -> None:
    # the setup's own Python error, if any, raised in the program
    if PyErr_Occurred() != 0:
        _raise()


if Py_IsInitialized() == 0:
    # embedded: CPython as it runs the script (its locale and UTF-8 mode, sys.executable, sys.argv, the
    # script's directory first on sys.path), without its signal handlers (Pystachy keeps its own); then
    # the GIL is released until an operation
    pye_preinit()
    Py_InitializeEx(0)
    try:
        if pye_init() == 0:
            _raise()
        _argv = PyList_New(0)
        _check()
        for _a in sys.argv:
            _s = PyUnicode_DecodeUTF8(_a, len(_a), "surrogateescape")  # (as CPython decodes arguments)
            _check()
            PyList_Append(_argv, _s)
            Py_DecRef(_s)
            _check()
        PySys_SetObject("argv", _argv)
        Py_DecRef(_argv)
        _check()
        _d = os.path.realpath(sys.argv[0])
        _d = _d[: _d.rfind("/")] if _d.rfind("/") > 0 else "/"
        _path = PySys_GetObject("path")  # (borrowed)
        _ins = PyObject_GetAttrString(_path, "insert")
        _check()
        _t = PyTuple_New(2)
        _check()
        PyTuple_SetItem(_t, 0, PyLong_FromLongLong(0))
        PyTuple_SetItem(_t, 1, PyUnicode_DecodeUTF8(_d, len(_d), "surrogateescape"))
        _check()
        _r = PyObject_Call(_ins, _t, 0)
        Py_DecRef(_t)
        Py_DecRef(_ins)
        if _r == 0:
            _raise()
        Py_DecRef(_r)
    finally:
        PyEval_SaveThread()
