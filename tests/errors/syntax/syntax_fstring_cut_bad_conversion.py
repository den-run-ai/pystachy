# error: syntax_fstring_cut_bad_conversion.py:5: error: '{' was never closed
# CPython checks a conversion character once it has parsed the whole field: in an f-string cut
# short, the error that cut it comes first
x = 1
print(f"{x!f
