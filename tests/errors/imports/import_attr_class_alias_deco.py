# error: class emods.attrdeco.C is not supported: its decorator @object.__new__ is not supported
# (no alias is made of a decorated class through a module's attribute: its decorator may bind the
# name to something else, here an instance, so the decorator's diagnostic stays)
import emods.attrdeco

A = emods.attrdeco.C
print(type(A).__name__)
