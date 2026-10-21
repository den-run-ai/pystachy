# sub imports fromcyc_alias, whose alias A = pkg.x.C reads x before the package's from-import has
# bound it, where the package's code imports sub first (tests/programs/imports/import_attr_class_alias_fromcycle.py)
class C:
    pass


import emods.fromcyc_alias
