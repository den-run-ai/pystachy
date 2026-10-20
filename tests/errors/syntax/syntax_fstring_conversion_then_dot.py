# error: syntax_fstring_conversion_then_dot.py:5: error: f-string: expecting ':' or '}'
# CPython checks a conversion character once it has parsed the whole field: a field that goes on
# after it is not one
x = 1
print(f"{x!f.real}")
