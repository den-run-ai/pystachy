# Documented deviation: a class of an imported module that Pystachy leaves uncompiled is not
# created when the module is imported, and what a builtin operation of its body raises is not
# reported where Pystachy does not evaluate the operation, as where it reads a name the body bound
# to other than a constant, or in the module's later classes (deftime_class_raises.py and
# class_consts_raise.py have ones that are). CPython fails at the first class: ValueError: 'x' in
# __slots__ conflicts with class variable (also Protocol[int], Job's field order, Ratio's 1 // n
# and Later's 1 // 0 are errors there).
import devmods.classes

print("main: done")
