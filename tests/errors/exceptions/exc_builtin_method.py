# error: BaseException.with_traceback() is not supported (of a builtin exception, str(e), repr(e) and formatting are)
try:
    int("x")
except ValueError as e:
    raise e.with_traceback(None)
