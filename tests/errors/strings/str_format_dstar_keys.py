# error: str_format_dstar_keys.py:4: error: ** of a dict[int,str] into the arguments of str.format() is not supported (of a dict[str, T], a function's **kwargs or a dict display with str keys, it is)
# ** of a dict whose keys are not strs (CPython raises TypeError: keywords must be strings)
d = {1: "a"}
print("{}".format(**d))
