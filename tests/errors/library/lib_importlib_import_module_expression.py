# error: lib_importlib_import_module_expression.py:5: error: expected _module_named_by_a_string_constant, got str
from importlib import import_module

# (a module is no value: the call binds a variable, mod = import_module("json"), or stands alone)
print(import_module("json").dumps([1]))
