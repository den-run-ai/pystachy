"""CPython's version of Pystachy's lib/pyobj.py: the same API over the running interpreter's own
objects (put this directory on PYTHONPATH). A Python exception is raised again as the first
builtin class in its __mro__ that Pystachy has, with the same str(), as lib/pyobj.py does. A
program may use what __all__ names (Pystachy rejects the rest at compile time); an Object comes
only from these functions and its methods."""
import builtins as _builtins
import importlib as _importlib
import operator as _operator
import sys as _sys

__all__ = ["Object", "Buffer", "import_module", "of_int", "of_float", "of_str", "of_list"]

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

    def buffer_f64(self, writable=False):
        return _guard(_buffer_open, _live(self._o), writable)

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


class Buffer:
    __slots__ = ("_root", "_count", "_offset", "_stride", "_readonly")

    def __init__(self, *args, **kwargs):
        raise TypeError("pyobj.Buffer() cannot be called: Object.buffer_f64 makes Buffers")

    def close(self):
        # Each derived view owns this memoryview independently. Its final reference
        # releases the export; close on a parent must not call memoryview.release().
        self._root = _CLOSED

    def __len__(self):
        _live(self._root)
        return self._count

    def dtype(self):
        _live(self._root)
        return "float64"

    def shape(self):
        return [len(self)]

    def strides(self):
        _live(self._root)
        return [self._stride]

    def offset(self):
        _live(self._root)
        return self._offset

    def nbytes(self):
        return 8 * len(self)

    def storage_nbytes(self):
        return _live(self._root).nbytes

    def readonly(self):
        _live(self._root)
        return self._readonly

    def view(self, start, count, step=1):
        root = _live(self._root)
        start, count, step = _as_int(start), _as_int(count), _as_int(step)
        if step == 0 or count < 0:
            raise ValueError("buffer view requires nonnegative count and nonzero step")
        if start < 0 or start > self._count or (count and start == self._count):
            raise IndexError("buffer view start out of range")
        stride = _buffer_i64(self._stride * step)
        last = _buffer_i64(start + _buffer_i64((count - 1) * step)) if count else start
        if count and not 0 <= last < self._count:
            raise IndexError("buffer view end out of range")
        offset = _buffer_i64(self._offset + _buffer_i64(start * self._stride)) if count else 0
        return _buffer_wrap(root, count, offset, stride, self._readonly)

    def _index(self, index):
        index = _as_int(index)
        if index < 0:
            index += self._count
        if index < 0 or index >= self._count:
            raise IndexError("buffer index out of range")
        return (self._offset + index * self._stride) // 8

    def get(self, index):
        return _live(self._root)[self._index(index)]

    def set(self, index, value):
        root = _live(self._root)
        if self._readonly:
            raise TypeError("buffer is read-only")
        root[self._index(index)] = value

    def dot(self, other):
        a, b = _live(self._root), _live(other._root)
        if self._count != other._count:
            raise ValueError("buffer dot requires equal lengths")
        total = 0.0
        ai, bi = self._offset // 8, other._offset // 8
        for _ in range(self._count):
            total += a[ai] * b[bi]
            ai += self._stride // 8
            bi += other._stride // 8
        return total


def _buffer_i64(value):
    if not -(2**63) <= value < 2**63:
        raise OverflowError("buffer view arithmetic overflow")
    return value


def _buffer_wrap(root, count, offset, stride, readonly):
    b = object.__new__(Buffer)
    b._root, b._count, b._offset, b._stride, b._readonly = root, count, offset, stride, readonly
    return b


def _buffer_open(o, writable):
    root = memoryview(o)
    try:
        if root.format != "d" or root.itemsize != 8:
            raise TypeError("buffer_f64 requires native float64 format 'd'")
        if root.ndim != 1:
            raise ValueError("buffer_f64 requires one dimension")
        if root.strides != (8,) or any(x >= 0 for x in root.suboffsets):
            raise ValueError("buffer_f64 requires contiguous direct storage")
        if writable and root.readonly:
            raise TypeError("buffer_f64 requires writable storage")
        return _buffer_wrap(root, len(root), 0, 8, not writable)
    except BaseException:
        root.release()
        raise


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

