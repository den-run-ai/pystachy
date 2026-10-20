# error: syntax_fstring_escape_after_field.py:4: error: invalid syntax. Perhaps you forgot a comma?
# CPython decodes an f-string's literal text once it has read its end: after its fields' errors
x = 1
print(f"\x{x 1}")
