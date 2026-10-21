# error: str_format_star_list.py:4: error: unpacking a list into the arguments of str.format() is supported only after the other positional arguments
# a list's items, whose number only run time knows, before another positional argument
xs = ["a", "b"]
print("{}{}{}".format(*xs, "c"))
