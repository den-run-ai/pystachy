# error: import_default_annotation.py:6: error: emods.anns.with_default() is not supported: parameter 'xs': unsupported type annotation
# An imported function whose annotated parameter Pystachy does not support evaluates its default
# value when its def runs, an error only where the program calls it (the default was compiled
# against a placeholder type: "expected int, got list[int]" at the import).
import emods.anns
print(emods.anns.count(), emods.anns.with_default())
