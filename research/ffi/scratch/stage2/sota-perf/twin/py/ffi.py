"""CPython twin of Pystachy's builtin ffi module (sketch): it defines what the boundary means,
so a program that uses @extern/@pycall prints the same under CPython and under Pystachy."""
import ctypes, ctypes.util, importlib, typing

c_int = typing.NewType("c_int", int)     # C int: i32, OverflowError outside its range
c_uint = typing.NewType("c_uint", int)   # C unsigned int: i32 zeroext
Ptr = typing.NewType("Ptr", int)         # an opaque C pointer, an int that is never dereferenced

_C = {int: ctypes.c_int64, float: ctypes.c_double, str: ctypes.c_char_p, bytes: ctypes.c_char_p,
      c_int: ctypes.c_int32, c_uint: ctypes.c_uint32, Ptr: ctypes.c_void_p, type(None): None}
_RANGE = {c_int: (-(1 << 31), (1 << 31) - 1), c_uint: (0, (1 << 32) - 1), int: (-(1 << 63), (1 << 63) - 1)}


def _exact(v, t, what):
    want = int if t in (c_int, c_uint, Ptr) else t
    if type(v) is not want:              # the compiler's rule: no int for float, no bool for int
        raise TypeError(f"{what}: expected {want.__name__}, got {type(v).__name__}")
    if t in _RANGE and not _RANGE[t][0] <= v <= _RANGE[t][1]:
        raise OverflowError(f"{what}: {v} does not fit in {t.__name__ if t is not int else 'int64'}")


def extern(lib):
    dll = ctypes.CDLL(ctypes.util.find_library(lib) or lib)
    def bind(stub):
        hints = typing.get_type_hints(stub)
        ret = hints.pop("return")
        names = list(hints)
        cf = getattr(dll, stub.__name__)
        cf.argtypes = [_C[hints[n]] for n in names]
        cf.restype = _C[ret]
        def call(*args):
            for n, a in zip(names, args):
                _exact(a, hints[n], f"{stub.__name__}() argument '{n}'")
            r = cf(*[a.encode("utf-8", "surrogatepass") if hints[n] is str else a for n, a in zip(names, args)])
            if ret is str:
                if r is None:
                    raise ValueError(f"{stub.__name__}() returned NULL")
                return r.decode("utf-8", "surrogatepass")
            return 0 if ret is Ptr and r is None else r
        call.__name__ = stub.__name__
        return call
    return bind


def _copy(v, t, what):                   # by value, as the compiled side converts it
    o = typing.get_origin(t)
    if o is list:
        _exact(v, list, what); return [_copy(x, typing.get_args(t)[0], what) for x in v]
    if o is dict:
        _exact(v, dict, what); k, w = typing.get_args(t); return {_copy(a, k, what): _copy(b, w, what) for a, b in v.items()}
    if o is tuple:
        _exact(v, tuple, what); return tuple(_copy(x, u, what) for x, u in zip(v, typing.get_args(t)))
    _exact(v, type(None) if t is None else t, what)
    return v


def pycall(module):
    def bind(stub):
        hints = typing.get_type_hints(stub)
        ret = hints.pop("return")
        fn = getattr(importlib.import_module(module), stub.__name__)   # when the def runs, as compiled code does
        def call(*args):
            r = fn(*[_copy(a, hints[n], f"{stub.__name__}() argument '{n}'") for n, a in zip(hints, args)])
            return _copy(r, ret, f"{stub.__name__}() result")
        call.__name__ = stub.__name__
        return call
    return bind


def byvalue(f):                          # ext mode: containers cross by copy, in both runs
    hints = typing.get_type_hints(f)
    ret = hints.pop("return")
    def call(*args):
        return _copy(f(*[_copy(a, hints[n], f"{f.__name__}() argument '{n}'") for n, a in zip(hints, args)]), ret, f"{f.__name__}() result")
    call.__name__ = f.__name__
    return call
