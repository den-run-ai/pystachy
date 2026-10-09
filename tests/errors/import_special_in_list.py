# error: import_special_in_list.py:5: error: unsupported type annotation
# Lists of Pair compare their items with Pair.__eq__, which cannot be compiled (its parameter is
# annotated object): an error where the program compares them, not an identity test.
import emods.special
print([emods.special.Pair(1)] == [emods.special.Pair(1)])
