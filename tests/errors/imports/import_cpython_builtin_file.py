# error: module '_symtable' is not supported: it is built into CPython, which imports it rather than the _symtable module on the module path, and Pystachy does not have it
# (#254) The program's directory holds a package _symtable (tests/_symtable/), which
# CPython never imports in place of its builtin module, so neither does Pystachy
import _symtable

print(_symtable.symtable)
