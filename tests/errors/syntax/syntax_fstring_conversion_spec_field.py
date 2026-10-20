# error: syntax_fstring_conversion_spec_field.py:5: error: f-string: invalid conversion character 'z': expected 's', 'r', or 'a'
# CPython checks a conversion character once it has parsed the whole field, spec and all: an
# invalid one in a field of the spec comes first
x = 1
print(f"{x!f:{x!z}}")
