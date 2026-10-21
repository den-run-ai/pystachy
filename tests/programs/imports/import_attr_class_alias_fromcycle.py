# An alias through a package's attribute that its own from-import binds (from . import sub as x), in
# a circular import that runs the alias's statement first: the package's code imports sub, whose
# code imports the alias's module before the from-import binds x. CPython's read of pkg.x.C raises
# AttributeError there, and so does the alias's (#804); only its type is printed, as the messages
# differ (docs/language/compatibility.md). import_attr_class_alias_fromcycle_first runs the other
# order
try:
    import emods.fromcyc
except AttributeError as e:
    print(type(e).__name__)
print("main")
