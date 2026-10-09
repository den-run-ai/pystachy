# Documented deviation: a class of an imported module that the program never uses is not created
# when the module is imported, and what the builtin operations of the code Pystachy leaves
# uncompiled there raise is not reported. CPython fails at the first class: ValueError: 'x' in
# __slots__ conflicts with class variable (also Protocol[int], Job's field order, Plain[int] and
# int | 3 are errors there).
import devmods.classes

print("main: done")
