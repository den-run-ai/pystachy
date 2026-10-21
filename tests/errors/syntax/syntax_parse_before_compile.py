# error: syntax_parse_before_compile.py:8: error: cannot assign to function call here. Maybe you meant '==' instead of '='?
def f(x):
    return x
    break


def g(x):
    h(x) = 1


print("ran")
