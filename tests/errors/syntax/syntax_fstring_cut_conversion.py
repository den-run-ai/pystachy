# error: syntax_fstring_cut_conversion.py:4: error: f-string: invalid conversion character 'z': expected 's', 'r', or 'a'
# (but for an error that CPython raises where it builds the field)
x = 1
y = x f"{x!z}
