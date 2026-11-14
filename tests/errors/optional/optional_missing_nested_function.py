# error: optional_missing_nested_function.py:5: error: module '_pystachy_absent_c' is not supported: it is not a builtin module and there is no _pystachy_absent_c.py on the module path (module 'absentmods.needs_c' imports it)
# A function's import of a module whose import of a missing module fails is an error where the
# function is compiled, as its import of a module that is not found is.
def late() -> None:
    import absentmods.needs_c
    print(absentmods.needs_c.version())


try:
    import absentmods.needs_c
except ImportError:
    print("fallback")
late()
