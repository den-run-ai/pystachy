# The ImportError of a module's code that no except clause of the optional import catches ends the
# program after that code, as in CPython.
try:
    import loader.broken
except ModuleNotFoundError:
    print("not this one")
print("not reached")
