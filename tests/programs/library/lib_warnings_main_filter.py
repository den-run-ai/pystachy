# The default filter that shows a DeprecationWarning of the main program is CPython's C module's,
# which keeps the str "__main__": only the module named __main__ matches it, not __main__.pkg or
# __main__x, whose warnings the next default filter ignores. (The warnings are recorded and
# printed, as only the last line of a test's stderr is compared.)
import warnings

with warnings.catch_warnings(record=True) as log:
    warnings.warn_explicit("a", DeprecationWarning, "f.py", 1, module="__main__.pkg")
    warnings.warn_explicit("b", DeprecationWarning, "f.py", 2, module="__main__x")
    warnings.warn_explicit("c", DeprecationWarning, "f.py", 3, module="__main__")
    warnings.warn_explicit("d", DeprecationWarning, "f.py", 4, module="pkg.__main__")
print([str(w.message) for w in log])
