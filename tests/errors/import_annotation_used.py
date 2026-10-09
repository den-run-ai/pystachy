# error: import_annotation_used.py:5: error: dict keys must be int or str
# An imported function whose annotation Pystachy does not support is an error where the program
# calls it, with the error typeof() reports (the program's calls of count() compile).
import emods.anns
print(emods.anns.count(), emods.anns.keys({1.5: 2}))
