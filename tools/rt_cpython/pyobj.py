"""CPython's version of Pystachy's lib/pyobj.py: the same API over the running interpreter's own
objects (put this directory on PYTHONPATH). A Python exception is raised again as the first
builtin class in its __mro__ that Pystachy has, with the same str(), as lib/pyobj.py does. A
program may use what __all__ names (Pystachy rejects the rest at compile time); an Object comes
only from these functions and its methods."""
import builtins as _builtins
import importlib as _importlib
import operator as _operator
import sys as _sys

__all__ = ["Object", "import_module", "of_int", "of_float", "of_str", "of_list"]

_BUILTIN = ["KeyError", "IndexError", "ZeroDivisionError", "OverflowError", "ValueError", "TypeError",
            "AttributeError", "ModuleNotFoundError", "ImportError", "NotImplementedError", "RecursionError",
            "RuntimeError", "FileNotFoundError", "OSError", "StopIteration", "AssertionError", "LookupError",
            "ArithmeticError", "EOFError", "KeyboardInterrupt", "SystemExit", "GeneratorExit", "Exception",
            "BaseException"]


_CLOSED = object()


def _live(o):
    if o is _CLOSED:
        raise ValueError("operation on a closed Python object")
    return o


def _builtin(e, again=True):
    # e as the builtin class Pystachy raises it as, with str(e); if str(e) raises, what it raised (once)
    k = next((c.__name__ for c in type(e).__mro__ if c.__name__ in _BUILTIN), "Exception")
    k = "RuntimeError" if k == "RecursionError" else k
    try:
        m = str(e)
    except Exception as e2:
        if not again:
            m = "<exception str() failed>"
        else:
            return _builtin(e2, False)
    return getattr(_builtins, k)(m)


def _guard(f, *a):
    try:
        return f(*a)
    except (SystemExit, KeyboardInterrupt):
        raise
    except BaseException as e:
        raise _builtin(e) from None


def _flush():
    # before a call: what was printed so far reaches sys.stdout's file first (a failure is dropped)
    try:
        if _sys.stdout is not None:
            _sys.stdout.flush()
    except Exception:
        pass


def _as_int(o):
    # PyLong_AsLongLong: __index__, then C's long long
    v = _operator.index(o)
    if not -2**63 <= v < 2**63:
        raise OverflowError("int too big to convert")
    return v


def _as_float(o):
    # PyFloat_AsDouble: a float, or __float__, or __index__ (no str: float() would parse it)
    if isinstance(o, float):
        return float(o)
    if hasattr(type(o), "__float__"):
        return float(o)
    if hasattr(type(o), "__index__"):
        return float(_operator.index(o))
    raise TypeError(f"must be real number, not {type(o).__name__}")


class Object:
    __slots__ = ("_o",)

    def __init__(self, *args, **kwargs):
        raise TypeError("pyobj.Object() cannot be called: import_module, of_int, of_float, of_str and of_list make Objects")

    def close(self):
        self._o = _CLOSED

    def attr(self, name):
        return _wrap(_guard(getattr, _live(self._o), name))

    def call(self, args):
        f, a = _live(self._o), [_live(x._o) for x in args]
        _flush()
        return _wrap(_guard(f, *a))

    def __getitem__(self, k):
        o, i = _live(self._o), _live(k._o)
        return _wrap(_guard(lambda: o[i]))

    def __len__(self):
        return _guard(len, _live(self._o))

    def __bool__(self):
        return _guard(bool, _live(self._o))

    def to_int(self):
        return _guard(_as_int, _live(self._o))

    def to_float(self):
        return _guard(_as_float, _live(self._o))

    def __str__(self):
        return _guard(str, _live(self._o))

    def __repr__(self):
        return _guard(repr, _live(self._o))


def _wrap(o):
    x = object.__new__(Object)
    x._o = o
    return x


def import_module(name):
    return _wrap(_guard(_importlib.import_module, name))


def of_int(v):
    return _wrap(v)


def of_float(x):
    return _wrap(x)


def of_str(s):
    return _wrap(s)


def of_list(xs):
    return _wrap([_live(x._o) for x in xs])

