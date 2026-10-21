# A class that its decorator replaces with an instance (@object.__new__), which
# tests/errors/imports/import_attr_class_alias_deco.py reads as emods.attrdeco.C
@object.__new__
class C:
    pass
