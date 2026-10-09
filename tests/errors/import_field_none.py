# error: import_field_none.py:5: error: class emods.hooks.Hooks is not supported: cannot infer the type of field 'ready'
# An imported class whose field would always hold None is an error only where the program uses
# it: the call of count() compiles, the use of the class does not.
import emods.hooks
print(emods.hooks.count(), emods.hooks.Hooks().n)
