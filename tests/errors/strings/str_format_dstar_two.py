# error: str_format_dstar_two.py:5: error: ** of more than one dict into the arguments of str.format() is not supported
# two dicts whose keys only run time knows (CPython raises TypeError for a key in both)
a = {"x": 1}
b = {"y": 2}
print("{x}{y}".format(**a, **b))
