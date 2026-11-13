# error: lib_importlib_import_module_relative.py:5: error: expected _module_named_by_a_string_constant, got str
import importlib

# (CPython: TypeError: the 'package' argument is required to perform a relative import for '.path')
mod = importlib.import_module(".path")
print(mod)
