# error: str_format_value.py:4: error: str.format is a method: call it on a string literal, "...".format(...) (methods are not values; map() takes "...".format)
# a literal's format() as a value, other than map()'s function
xs = [1, 2]
show = "<{}>".format
print([show(x) for x in xs])
