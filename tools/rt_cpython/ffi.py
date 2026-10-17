"""CPython's version of Pystachy's ffi module, so that a program that declares C functions with
@extern runs under CPython too (put this directory on PYTHONPATH): ctypes calls the same C
function, with the checks Pystachy's stubs make. A str goes in as its UTF-8 bytes (const char *,
NUL-terminated; a NUL in it is a ValueError) and a returned char * comes back as a str (NULL:
None, or a ValueError for -> str); C integers are range-checked (OverflowError), as Pystachy
checks them. A list[float] or list[c_int64] goes in as a C array of its items (double *,
int64_t *), copied back into the list when the call returns, since Pystachy passes the list's own
items, which C may write: one array for each distinct list, so that a list passed for two
parameters is one array to C, as it is one in Pystachy."""
import ast as _ast
import ctypes
import functools as _functools
import inspect as _inspect
import operator as _operator
import threading as _threading
import typing


class c_int(int):
    """C's int (32 bits) in an @extern function's signature; an int everywhere else"""


class c_uint(int):
    """C's unsigned int"""


class c_int64(int):
    """int64_t (long long)"""


class c_ssize_t(int):
    """ssize_t / Py_ssize_t"""


class c_uint64(int):
    """uint64_t"""


class c_size_t(int):
    """size_t"""


class c_buf(str):
    """a str's UTF-8 bytes (NULs allowed) for a C function that also takes their length"""


class c_void_p(int):
    """a pointer, as an int (NULL is 0)"""


class c_float(float):
    """C's float (32 bits) in an @extern function's signature; a float everywhere else"""


_C = {c_int: ctypes.c_int, c_uint: ctypes.c_uint, c_int64: ctypes.c_int64, c_ssize_t: ctypes.c_ssize_t,
      c_uint64: ctypes.c_uint64, c_size_t: ctypes.c_size_t, c_void_p: ctypes.c_void_p,
      c_buf: ctypes.c_char_p, float: ctypes.c_double, c_float: ctypes.c_float, str: ctypes.c_char_p, type(None): None, typing.Optional[str]: ctypes.c_char_p}


# the lists an @extern function takes: their item type in a C array
_LISTS = {list[float]: ctypes.c_double, list[c_int64]: ctypes.c_int64, list[c_ssize_t]: ctypes.c_int64,
          typing.List[float]: ctypes.c_double, typing.List[c_int64]: ctypes.c_int64, typing.List[c_ssize_t]: ctypes.c_int64}


def _check(t, v):
    if t is str:
        if "\0" in v:
            raise ValueError("embedded null character")
        return v.encode("utf-8", "surrogatepass")
    if t is c_buf:
        return v.encode("utf-8", "surrogatepass")
    if t is float or t is c_float:
        return float(v)  # (ctypes rounds a c_float argument to the nearest float, as C does)
    if t is c_int and not -2**31 <= v < 2**31:
        raise OverflowError("Python int too large to convert to C int")
    if t in (c_uint, c_uint64, c_size_t) and v < 0:
        raise OverflowError("can't convert negative int to unsigned")
    if t is c_uint and v >= 2**32:
        raise OverflowError("Python int too large to convert to C unsigned int")
    if t in (c_int64, c_ssize_t, c_uint64, c_size_t, c_void_p) and not -2**63 <= v < 2**63:
        raise OverflowError("int too big to convert")  # (Pystachy's int is 64-bit: checked where it was made)
    return v


def _s(b):
    return None if b is None else b.decode("utf-8", "surrogatepass")


def extern(lib, symbol=""):
    # the def's own signature binds a call's arguments (keywords and defaults as for any def), then
    # ctypes calls the C function, found when the def runs, as Pystachy finds it then
    def deco(f):
        hints = typing.get_type_hints(f)
        ret = hints.pop("return")
        sig = _inspect.signature(f)
        ts = [hints[p] for p in sig.parameters]
        for t in ts + [ret]:
            if t is int:
                raise TypeError(f"C function {f.__name__}() takes or returns int: say which C integer type")
        for t in [x for x in ts if typing.get_origin(x) is list and x not in _LISTS] + ([ret] if typing.get_origin(ret) is list else []):
            raise TypeError(f"C function {f.__name__}() takes or returns {t}: a list goes only as an argument, list[float] or list[c_int64]")
        cf = getattr(ctypes.CDLL(lib or None), symbol or f.__name__)
        cf.argtypes = [ctypes.POINTER(_LISTS[t]) if t in _LISTS else _C[t] for t in ts]
        cf.restype = _C[ret]

        def call(*args, **kwargs):
            b = sig.bind(*args, **kwargs)
            b.apply_defaults()
            arrays = {}  # (id of a list: the list and its C array)
            cargs = []
            for t, p in zip(ts, sig.parameters):
                v = b.arguments[p]
                if t in _LISTS:
                    if id(v) not in arrays:
                        items = [float(x) for x in v] if _LISTS[t] is ctypes.c_double else [_check(c_int64, x) for x in v]
                        arrays[id(v)] = (v, (_LISTS[t] * len(v))(*items))
                    cargs.append(arrays[id(v)][1])
                else:
                    cargs.append(_check(t, v))
            r = cf(*cargs)
            for v, a in arrays.values():
                v[:] = list(a)  # (what C wrote, once for each list)
            if ret is str and r is None:
                raise ValueError("a C function declared -> str returned NULL")
            if ret is c_void_p:
                return r or 0  # (ctypes gives None for NULL)
            if ret in (c_uint64, c_size_t) and r >= 2**63:
                raise OverflowError("C unsigned result is too large for int")
            return _s(r) if ret in (str, typing.Optional[str]) else r

        call.__name__ = f.__name__
        return call

    return deco


def string_at(addr, n):
    if n < 0:
        raise ValueError("ffi.string_at() takes a length >= 0")  # (ctypes reads up to a NUL)
    return _s(ctypes.string_at(addr, n))


# @export: a function of a module that `pystachy ext` compiles into a CPython extension module.
# Under CPython the module's source runs, and this wrapper makes each call what pyext.c's
# trampoline makes it: positional arguments only, converted and checked as the extension
# converts them, results checked against Pystachy's 64-bit int, only the importing thread may
# call, and an exception leaves as the builtin class Pystachy raises it as (its nearest builtin
# base for one of the module's own classes) with args rebuilt from their repr, else (str(e),).


def _in(name, i, t, x):
    if t is int:
        v = _operator.index(x)
        if not -2**63 <= v < 2**63:
            raise OverflowError("int too big to convert")
        return v
    if t is float:
        if not (hasattr(type(x), "__float__") or hasattr(type(x), "__index__")):
            raise TypeError(f"must be real number, not {type(x).__name__}")
        return float(x)
    if t is bool:
        if x is not True and x is not False:
            raise TypeError(f"{name}() argument {i + 1} must be bool")
        return x
    if not isinstance(x, str):
        raise TypeError("expected str")
    return x[:]  # (a plain str)


def _out(t, r):
    if t is int and not -2**63 <= r < 2**63:
        raise OverflowError("integer result does not fit in 64 bits")
    return float(r) if t is float else r


def export(f):
    hints = _typing_hints(f)
    ret = hints.pop("return")
    ts = list(hints.values())
    owner = _threading.get_ident()
    name = f.__name__

    @_functools.wraps(f)
    def call(*args, **kw):
        if _threading.get_ident() != owner:
            raise RuntimeError(f"{name}() is compiled by Pystachy, whose runtime is single-threaded: call it from the thread that imported its module")
        if kw:
            raise TypeError(f"{name}() takes no keyword arguments")
        if len(args) != len(ts):
            raise TypeError(f"{name}() takes {len(ts)} positional arguments but {len(args)} were given")
        a = [_in(name, i, t, x) for i, (t, x) in enumerate(zip(ts, args))]
        try:
            return _out(ret, f(*a))
        except BaseException as e:
            c = type(e)
            if c.__module__ != "builtins":
                c = next(k for k in c.__mro__ if k.__module__ == "builtins")
            try:
                ea = _ast.literal_eval(repr(e.args))
            except Exception:
                ea = (str(e),)
            raise c(*ea) from None

    return call


def _typing_hints(f):
    return typing.get_type_hints(f)
