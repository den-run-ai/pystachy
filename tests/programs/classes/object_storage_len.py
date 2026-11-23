# len() of a value of object that isinstance() has not narrowed: its result is an int whatever the
# value holds, so the type it holds answers it (object_conversions.py)
x: object = "abc"
print(len(x))
