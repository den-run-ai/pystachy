# error: syntax_fstring_cut_debug_empty.py:5: error: f-string: valid expression required before '='
# a field that is only '=', in an f-string cut short: CPython's parser reports it before the
# error that cut it
x = 1
print(f"{=
