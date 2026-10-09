# error: syntax_bytes_mix.py:4: error: cannot mix bytes and nonbytes literals
def f(x):
    return ("a"
            b"b")


print("ran")
