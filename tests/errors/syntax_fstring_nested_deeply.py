# error: syntax_fstring_nested_deeply.py:5: error: f-string: expressions nested too deeply
# (a format spec may hold fields two levels deep)
def f(x, y, z, w):
    a = f"{x:{y:{z}}}"
    return f"{x:{y:{z:{w}}}}"


print("ran")
