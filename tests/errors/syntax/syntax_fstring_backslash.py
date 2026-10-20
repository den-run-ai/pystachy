# error: syntax_fstring_backslash.py:5: error: unexpected character after line continuation character
# a backslash in a field's expression may only continue a line
x = 1
print(f"{x \
+ 1}", f"{x \ }")
