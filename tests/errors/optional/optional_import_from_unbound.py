# error: the code of module 'eload.unsure2' may raise ImportError, which the except clause would catch
# (its from-import takes a name that eload.unsure's code may leave unbound)
try:
    import eload.unsure2
except ImportError:
    print("fallback")
