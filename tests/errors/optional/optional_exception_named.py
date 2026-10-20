# error: module 'eload.broken' raises ImportError as it initializes, and an except clause that re-raises or names the exception is not supported
try:
    import eload.broken
except ImportError as e:
    print("fallback", e)
