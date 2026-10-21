# An alias of a class through a module's attribute (#804) in a circular import: y imports x as
# cx, which imports y back and then binds K, so that K is bound when y's alias A = cx.K reads it.
# (Through the package, A = mods.attralias_cyc_x.K, it stays an error: see
# tests/errors/imports/import_attr_class_alias_subcycle.py)
import mods.attralias_cyc_y
import mods.attralias_cyc_x

print(mods.attralias_cyc_y.make().n, isinstance(mods.attralias_cyc_y.A(), mods.attralias_cyc_x.K))
