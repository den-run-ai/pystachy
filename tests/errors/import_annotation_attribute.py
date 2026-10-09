# error: emods/attrann.py:4: error: module 'emods.mod' has no attribute 'Undefined'
# An annotation that reads an attribute a module does not have fails the import of the module
# whose def evaluates it, used or not (an AttributeError in CPython).
import emods.attrann

print(emods.attrann.g())
