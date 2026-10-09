# error: import_template_annotation.py:5: error: unsupported type annotation
# A call of an imported template whose annotated parameter Pystachy does not support reports the
# annotation, not the argument against a placeholder type (it was "expected int, got list[int]").
import emods.anns
print(emods.anns.count(), emods.anns.mixed(1, [1, 2]))
