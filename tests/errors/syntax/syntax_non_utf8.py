# error: syntax_non_utf8.py:5: error: Non-UTF-8 code starting with '\xe9' in file
# a file without a coding declaration is UTF-8; CPython reads it a line at a time
def f(x):
    return x + 1
    return "café"


print("ran")
