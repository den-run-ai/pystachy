# error: class 'mods.attralias_cyc_x.K' cannot be used as a value
# (an alias of a class through a module's attribute (#804) in a circular import stays an error: y
# imports x as cx, whose code imports y back, so another module's code runs before y's alias
# A = cx.K binds A and may read it. Imported in this order CPython runs it, as x binds K first)
import mods.attralias_cyc_y
import mods.attralias_cyc_x

print(mods.attralias_cyc_y.make().n, isinstance(mods.attralias_cyc_y.A(), mods.attralias_cyc_x.K))
