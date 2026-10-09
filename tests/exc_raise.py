# raise statements: of builtin classes with no, one or several arguments, of a caught exception,
# bare (re-raising the exception being handled, which every way out of a handler restores), and
# raise ... from ...


def reraise_here(n: int) -> None:
    try:
        if n == 0:
            raise KeyError("k")
        raise ValueError("v", n)
    except KeyError:
        print("re-raising")
        raise


def outer_handler() -> None:
    # a bare raise in a function an except clause calls: the exception being handled there
    raise


for n in range(2):
    try:
        reraise_here(n)
    except LookupError as e:
        print("lookup", repr(e))
    except ValueError as e:
        print("value", repr(e), str(e))
try:
    try:
        raise TypeError("inner")
    except TypeError:
        outer_handler()
except TypeError as e:
    print("from the caller's handler", e)
try:
    raise
except RuntimeError as e:
    print("no active", e)
try:
    try:
        raise ValueError("first")
    except ValueError:
        try:
            raise KeyError("second")
        except KeyError:
            pass
        raise
except ValueError as e:
    print("the handled one again:", e)
try:
    try:
        raise OSError("disk")
    except OSError as e:
        raise RuntimeError("wrapped") from e
except RuntimeError as e:
    print("from", e)
try:
    raise ValueError("no cause") from None
except ValueError as e:
    print(e)
try:
    raise IndexError
except IndexError as e:
    print("class alone:", repr(e), "[" + str(e) + "]")
try:
    raise KeyError(3)
except KeyError as e:
    print(repr(e), e)
try:
    raise ValueError(3.5, "x", True)
except ValueError as e:
    print(repr(e), e)
try:
    raise ValueError(7)
except ValueError as e:
    print(repr(e), e, f"{e}|{e!r}", "%s %r" % (e, e))
try:
    raise IOError("io")
except EnvironmentError as e:
    print(repr(e))
try:
    raise NotImplementedError("later")
except RuntimeError as e:
    print("subclass", repr(e))
try:
    raise ModuleNotFoundError("nope")
except ImportError as e:
    print(repr(e))
try:
    raise SyntaxError("bad syntax")
except SyntaxError as e:
    print(repr(e), e)
try:
    raise TabError()
except IndentationError as e:
    print(repr(e), e)
caught = ValueError("unused")
try:
    raise AssertionError("kept")
except AssertionError as e:
    caught = e
print("kept:", repr(caught))
try:
    raise caught
except AssertionError as e:
    print("raised again:", e)
try:
    assert len(str(caught)) > 100, "too short"
except AssertionError as e:
    print("assert:", e)
