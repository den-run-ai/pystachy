# Documented deviation: a class of an imported module that the program never uses is not created
# when the module is imported, so the errors CPython raises while creating it are not reported.
# CPython fails at the first class: ValueError: 'x' in __slots__ conflicts with class variable
# (also Protocol[int] and Job's field order are errors there).
import devmods.classes

print("main: done")
