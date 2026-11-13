# error: class mods.opmismatch.Labels is not supported: class 'Branch' cannot be used as a value
# An imported class whose annotation is not its value's type is compiled only where the
# program uses it: CPython checks no annotation, so the module still imports.
from mods.opmismatch import Labels

print(Labels.NAME)
