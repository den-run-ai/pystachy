# importlib.machinery's suffix lists are Pystachy's own: it compiles source modules and loads
# neither bytecode nor extension modules, so those lists are empty. CPython's name its .pyc
# files and the extension modules of its build, such as '.cpython-313-x86_64-linux-gnu.so'.
import importlib.machinery

print(importlib.machinery.BYTECODE_SUFFIXES, importlib.machinery.EXTENSION_SUFFIXES)
print(importlib.machinery.all_suffixes())
