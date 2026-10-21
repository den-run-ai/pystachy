# error: syntax_fstring_doubled_brace_escape.py:5: error: (unicode error) 'unicodeescape' codec can't decode bytes in position 0-2: truncated \xXX escape
# CPython decodes an f-string's text to each doubled brace on its own: the escape's position
# counts from the brace
x = 1
print(f"{x}a}}\x4")
