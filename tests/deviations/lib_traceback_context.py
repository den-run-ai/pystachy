# Documented deviation: Pystachy keeps no exception context (__context__), so traceback's lines of
# an exception that another one's handling caused are its own alone (lib/compatibility.md#traceback),
# where CPython first shows the exception being handled and "During handling of the above
# exception, another exception occurred:"; the frame lines that only CPython has are left out
import traceback

try:
    try:
        raise KeyError("first")
    except KeyError:
        raise ValueError("second")
except ValueError as e:
    print([ln for ln in traceback.format_exception(e) if not ln.startswith(("Traceback", "  "))])
