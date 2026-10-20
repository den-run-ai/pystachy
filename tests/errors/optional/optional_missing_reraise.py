# error: module 'eload.absent' is not supported
try:
    import eload.absent
except ImportError:
    print("fallback")
    raise
