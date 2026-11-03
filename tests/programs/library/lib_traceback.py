# lib/traceback.py: Pystachy keeps no tracebacks, so an exception formats as CPython formats one
# whose __traceback__ is None. An exception that was never raised has none in CPython either, so
# its lines are compared whole; of a raised one, the frame lines that only CPython has are left out
import io
import sys
import traceback


class AppError(Exception):
    pass


class Quiet(Exception):
    def __str__(self) -> str:
        return ""


def frameless(lines: list[str]) -> list[str]:
    return [ln for ln in lines if not ln.startswith("Traceback") and not ln.startswith("  ")]


print(traceback.format_exception_only(ValueError("x")))
print(traceback.format_exception_only(ValueError, ValueError("legacy")))
print(traceback.format_exception_only(AppError("app")), traceback.format_exception_only(Quiet()))
print(traceback.format_exception_only(KeyError("k")), traceback.format_exception_only(None))
print(traceback.format_exception(TypeError("never raised")))
print(traceback.format_exception(OSError, OSError(2, "gone"), None))
buf = io.StringIO()
traceback.print_exception(AppError("to a file"), file=buf)
print(repr(buf.getvalue()))
print(traceback.format_exc(), end="")
traceback.print_exc(file=buf)
print(repr(buf.getvalue().splitlines()[-1]))


def boom() -> None:
    raise AppError("bad thing")


try:
    boom()
except AppError as e:
    print(frameless(traceback.format_exception(e)))
    print(repr(traceback.format_exc().splitlines()[-1]))
    s = io.StringIO()
    traceback.print_exc(file=s)
    print(frameless(s.getvalue().splitlines()))
try:
    try:
        raise KeyError("inner")
    except KeyError as k:
        raise ValueError("outer") from k
except ValueError as v:
    print(frameless(traceback.format_exception(v)))
    print(frameless(traceback.format_exception(v, chain=False)))
try:
    try:
        raise OSError("first")
    except OSError as o:
        raise RuntimeError("") from o
except RuntimeError as r:
    lines = frameless(traceback.format_exception(r))
    print(lines)
print(traceback.extract_tb(None), traceback.format_tb(None), traceback.format_list([]))
try:
    traceback.format_exception(3)
except TypeError as e:
    print("TypeError:", e)
print(sys.exception())
