# error: tests/ffi/errors/py_modattr.py:4: error: pyobj._text is not offered by Pystachy's pyobj module, whose names are Object, import_module, of_int, of_float, of_str, of_list
import pyobj

print(pyobj._text(0, ""))
