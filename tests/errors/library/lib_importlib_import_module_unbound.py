# error: lib_importlib_import_module_unbound.py:6: error: importlib.import_module() is supported where a string constant names the module and the call binds one variable or stands alone
# (CPython: UnboundLocalError, as the function's own import of importlib runs after the call; an
# import statement in the call's place would import json)

def load() -> None:
    mod = importlib.import_module("json")
    print(mod.dumps([1]))
    import importlib


load()
