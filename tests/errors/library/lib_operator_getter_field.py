# error: lib_operator_getter_field.py:6: error: cannot assign to field '_items' of itemgetter: it holds a constant of the literal arguments the object was made with
# The constants a getter of literal items reads cannot change
from operator import itemgetter

g = itemgetter(1)
g._items = (2,)
print(g([1, 2, 3]))
