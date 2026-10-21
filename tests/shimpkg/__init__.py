# A package whose try reads the name of its submodule, which its from-import binds in CPython
# (tests/errors/language/name_error_shim_submodule.py)
from .sub import VALUE

try:
    module = sub  # noqa: F821
except NameError:
    module = None
print(VALUE, module is None)
