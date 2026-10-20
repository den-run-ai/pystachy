# error: syntax_fstring_conversion_spec_limitation_cut_after.py:5: error: f-string: invalid conversion character 'f': expected 's', 'r', or 'a'
# CPython checks a conversion character once its field ends, before the error that cut the
# f-string short after it: a Pystachy limitation in that field's spec gives way to it
x = 1
print(f"{x!f:{é}}{x
