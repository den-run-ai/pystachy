# error: the code that runs in the try may raise ImportError through a call (function require() may raise it), which the except clause would catch
def require() -> None:
    raise ImportError("required")


try:
    import eload.fine

    require()
except ImportError:
    print("fallback")
