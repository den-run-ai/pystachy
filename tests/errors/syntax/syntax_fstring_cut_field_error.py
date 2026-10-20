# error: syntax_fstring_cut_field_error.py:5: error: invalid syntax
# CPython's parser reads the fields of an f-string after an expression without its rules for
# errors, so an error in one is plain invalid syntax (before the error that cut it short)
x = 1
y = x f"{x 1}
