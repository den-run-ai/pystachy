# error: lib_importlib_import_module_relative.py:5: error: importlib.import_module() is supported where a string constant names the module and the call binds one variable or stands alone
import importlib

# (CPython: TypeError: the 'package' argument is required to perform a relative import for '.path')
mod = importlib.import_module(".path")
print(mod)
