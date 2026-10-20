# error: syntax_fstring_conversion_spec_limitation.py:5: error: f-string: invalid conversion character 'f': expected 's', 'r', or 'a'
# a Pystachy limitation in the spec of a field with an invalid conversion character does not
# come before CPython's error for that character
x = 1
print(f"{x!f:{é}}")
