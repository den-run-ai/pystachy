# error: the code of module 'eload.outer' may raise ImportError
try:
    import eload.outer
except ImportError:
    print("fallback")
