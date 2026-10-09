# error: cannot import name 'nothere' from 'eload.sub', and an except clause that re-raises or names the exception is not supported
try:
    from eload.sub import nothere
except ImportError as e:
    print("fallback", e)
