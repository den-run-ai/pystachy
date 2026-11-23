# error: object of type 'object' has no len() (narrow a value of object with isinstance() to int, float, bool, str, bytes, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# isinstance(x, list) narrows nothing, as the list's item type is not known (nor a dict's, a
# tuple's or a set's): len() of x stays an operation of a value of object
x: object = [1, 2]
if isinstance(x, list):
    print(len(x))
