# error: str_format_star_str.py:3: error: unpacking a str into the arguments of str.format() is not supported (a tuple's or a list's items are)
# a str's characters as the arguments
print("{}{}".format(*"ab"))
