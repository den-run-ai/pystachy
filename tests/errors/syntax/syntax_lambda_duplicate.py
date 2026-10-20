# error: syntax_lambda_duplicate.py:3: error: duplicate argument 'a' in function definition
def f(x):
    return lambda a, a: a


print("ran")
