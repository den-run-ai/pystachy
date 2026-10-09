# A module whose own optional import comes before its top-level raise of ImportError, or whose
# handler raises ImportError (a module that requires one that fails): an optional import of it
# runs the handler, and an import that is not optional ends the program with its exception.
try:
    import loader.broken2
except ImportError:
    print("fallback 2")
try:
    import loader.broken3
except ImportError:
    print("fallback 3")
import loader.broken3
