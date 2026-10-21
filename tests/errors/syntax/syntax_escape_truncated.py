# error: syntax_escape_truncated.py:3: error: (unicode error) 'unicodeescape' codec can't decode bytes in position 3-5: truncated \xXX escape
def f(x):
    return "abc\x4"


print("ran")
