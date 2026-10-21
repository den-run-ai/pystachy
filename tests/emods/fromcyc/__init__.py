# A package that binds its submodule by a from-import, whose code imports the module of an alias read
# through that name (tests/errors/imports/import_attr_class_alias_fromcycle.py)
from . import sub as x
