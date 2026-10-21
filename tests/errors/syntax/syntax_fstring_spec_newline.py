# error: syntax_fstring_spec_newline.py:5: error: f-string: newlines are not allowed in format specifiers for single quoted f-strings
# (the line of the newline)
def f(x):
    return f"{x
:
}"


print("ran")
