# error: import_descriptor_get.py:4: error: class emods.descriptor_get.Holder is not supported: a class attribute whose class defines __get__ is not supported (CPython calls it where the attribute is used)
from emods.descriptor_get import Holder

print(Holder().x)
