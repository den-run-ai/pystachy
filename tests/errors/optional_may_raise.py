# error: the code of module 'eload.maybe' may raise ImportError, which the except clause would catch
try:
    import eload.maybe
except ImportError:
    print("fallback")
