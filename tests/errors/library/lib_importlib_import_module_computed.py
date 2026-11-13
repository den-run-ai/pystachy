# error: lib_importlib_import_module_computed.py:8: error: expected _module_named_by_a_string_constant, got str
import importlib
import sys

# (a name the program computes: Pystachy compiles a program's modules with it, and cannot
# import one that only the run names)
name = "js" + ("on" if len(sys.argv) >= 0 else "")
mod = importlib.import_module(name)
print(mod.dumps([1]))
