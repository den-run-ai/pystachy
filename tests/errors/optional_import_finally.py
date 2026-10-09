# error: there is no no_such_module_zz.py on the module path; an optional import is supported only as try: <imports> / except ImportError: (except clauses naming only ImportError or ModuleNotFoundError, and no finally)
try:
    import no_such_module_zz
except ImportError:
    print("missing")
finally:
    print("finally")
