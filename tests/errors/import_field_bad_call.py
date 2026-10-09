# error: import_field_bad_call.py:5: error: class emods.anns.Holder is not supported: emods.anns.Holder.helper() is not supported: return annotation: None/Optional is only supported for class types, not int
# A field set from a call of a method whose annotation Pystachy does not support: the class is
# an error where it is used, with the annotation's error (not "cannot infer the type of field").
import emods.anns
print(emods.anns.count(), emods.anns.Holder().y)
