# A module that catches the ImportError its own code raises (tests/programs/exceptions/exc_import_selfcatch.py)
try:
    raise ImportError("handled inside")
except ImportError:
    print("selfcatch handled its own ImportError")
try:
    import no_such_module_zz
except ImportError:
    print("no no_such_module_zz")
VALUE = 5
