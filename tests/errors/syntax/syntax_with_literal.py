# error: syntax_with_literal.py:3: error: cannot assign to literal
def f(x):
    with x as 1:
        pass


print("ran")
