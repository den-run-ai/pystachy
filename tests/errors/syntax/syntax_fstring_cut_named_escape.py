# error: syntax_fstring_cut_named_escape.py:4: error: unterminated f-string literal (detected at line 4)
# a Pystachy limitation in an f-string cut short does not come before the error that cut it
x = 1
print(f"{x:\N{BULLET}}
