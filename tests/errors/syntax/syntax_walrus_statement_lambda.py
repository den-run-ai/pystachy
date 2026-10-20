# error: syntax_walrus_statement_lambda.py:4: error: cannot use assignment expressions with lambda
# (CPython's parser also tries a statement's first expressions as named expressions)
def f(x):
    lambda: x := 1


print("ran")
