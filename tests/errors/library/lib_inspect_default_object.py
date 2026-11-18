# error: lib_inspect_default_object.py:9: error: unsupported type annotation
# mypyc/ir/func_ir.py's shape, in a module that does not opt in to dynamic Any: a variable
# annotated object holds the marker and then a default of another type. One variable has one
# type here; a module that opts in annotates it Any
# (tests/programs/library/lib_inspect_any.py), and another passes each default itself
# (tests/mods/inspect_text_signature.py)
import inspect

default: object = inspect.Parameter.empty
default = 5
print(inspect.Parameter("x", inspect.Parameter.KEYWORD_ONLY, default=default))
