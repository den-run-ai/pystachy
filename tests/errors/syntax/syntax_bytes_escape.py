# error: syntax_bytes_escape.py:3: error: (value error) invalid \x escape at position 2
def f(x):
    return b"ab\x4"


print("ran")
