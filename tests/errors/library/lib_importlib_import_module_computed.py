# error: lib_importlib_import_module_computed.py:8: error: importlib.import_module() is supported where a string constant names the module and the call binds one variable or stands alone
import importlib
import sys

# (a name the program computes: Pystachy compiles a program's modules with it, and cannot
# import one that only the run names)
name = "js" + ("on" if len(sys.argv) >= 0 else "")
mod = importlib.import_module(name)
print(mod.dumps([1]))
