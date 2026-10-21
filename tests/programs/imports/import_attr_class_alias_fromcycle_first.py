# The circular import of import_attr_class_alias_fromcycle, from the alias's module: its import of
# the package runs the package's code to its end, which binds x, before the alias's statement reads
# pkg.x.C, so A is an alias of the class (#804)
import emods.fromcyc_alias

print("main")
