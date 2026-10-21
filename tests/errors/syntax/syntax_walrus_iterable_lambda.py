# error: syntax_walrus_iterable_lambda.py:3: error: assignment expression cannot be used in a comprehension iterable expression
def f(c):
    return [a for a in (lambda: (z := c))()]


print("ran")
