# error: syntax_fstring_cut_escape.py:4: error: unterminated f-string literal (detected at line 4)
# CPython decodes an f-string's literal text once it has read its end, never in one cut short
name = "a"
print(f"C:\Users\{name}
