# An alias of a class through the attribute that its package's from-import binds
# (tests/errors/imports/import_attr_class_alias_fromcycle.py)
import emods.fromcyc as pkg

A = pkg.x.C
print("fromcyc_alias:", A.__name__)
print("fromcyc_alias:", isinstance(A(), pkg.x.C))
