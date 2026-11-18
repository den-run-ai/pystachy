# error: module 'absentmods.needs_c' raises ModuleNotFoundError as it initializes, and an except clause that re-raises or names the exception is not supported
try:
    import absentmods.needs_c
except ImportError as e:
    print("fallback", e)
