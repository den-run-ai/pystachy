# A file without the .py suffix is no module, and only a directory is a portion of a namespace
# package (#1166): tests/extless/extless_plain is a text file, so the fallback runs, as in CPython.
try:
    import extless_plain
    print("imported extless_plain")
except ImportError:
    print("fallback: no module extless_plain")
