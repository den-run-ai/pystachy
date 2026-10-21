# error: class 'emods.fromcyc.sub.C' cannot be used as a value
# (an alias through a package's attribute that its own from-import binds (from . import sub as x),
# in a circular import, stays an error: fromcyc_alias imports the package, whose code imports sub,
# whose code imports fromcyc_alias back. Imported package first, CPython's read of pkg.x.C raises
# AttributeError there, which this catches)
try:
    import emods.fromcyc
except AttributeError as e:
    print(type(e).__name__)
print("main")
