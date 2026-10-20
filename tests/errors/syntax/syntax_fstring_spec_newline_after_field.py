# error: syntax_fstring_spec_newline_after_field.py:5: error: unterminated f-string literal (detected at line 5)
# after a field in a format spec, a newline ends a single-quoted f-string
x = 1
y = 2
print(f"{x:{y}
}")
