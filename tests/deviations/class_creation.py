# Documented deviation: a class of an imported module that Pystachy leaves uncompiled is not
# created when the module is imported, and what the builtin operations of its body raise is not
# reported. CPython fails at the first class: ValueError: 'x' in __slots__ conflicts with class
# variable (also Protocol[int], Job's field order and Ratio's 1 // 0 are errors there).
import devmods.classes

print("main: done")
