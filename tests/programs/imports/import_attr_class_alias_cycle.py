# An alias of a class through a module's attribute (#804) in a circular import: y imports x,
# which imports y back and then binds K, so that K is bound when y's alias A = x.K reads it
import mods.attralias_cyc_y
import mods.attralias_cyc_x

print(mods.attralias_cyc_y.make().n, isinstance(mods.attralias_cyc_y.A(), mods.attralias_cyc_x.K))
