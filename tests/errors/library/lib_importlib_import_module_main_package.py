# error: lib_importlib_import_module_main_package.py:6: error: importlib.import_module() is supported where a string constant names the module and the call binds one variable or stands alone
# (CPython: TypeError, as the main program's __package__ is None: no package for a relative name)
from importlib import import_module

print("start")
mod = import_module(".json", __package__)
