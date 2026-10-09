# error: import_special_len.py:5: error: __len__ must return int
# A special method of an imported class that does not have the shape Pystachy calls is an
# error only where the program uses it: Bag() and its field compile, len() does not.
import emods.special
print(emods.special.Bag(2).n, len(emods.special.Bag(2)))
