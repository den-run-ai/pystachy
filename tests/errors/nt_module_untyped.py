# error: nt_module_untyped.py:4: error: class emods.records.Untyped is not supported: parameter 'x' of method f() has no type annotation
from emods.records import Fine, Untyped

print(Fine(1), Untyped(1))
