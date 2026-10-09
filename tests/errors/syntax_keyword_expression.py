# error: syntax_keyword_expression.py:3: error: expression cannot contain assignment, perhaps you meant "=="?
def f(x):
    return g(x.y=1)


print("ran")
