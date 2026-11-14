# error: lib_importlib_import_module_expression.py:5: error: importlib.import_module() is supported where a string constant names the module and the call binds one variable or stands alone
from importlib import import_module

# (a module is no value: the call binds a variable, mod = import_module("json"), or stands alone)
print(import_module("json").dumps([1]))
