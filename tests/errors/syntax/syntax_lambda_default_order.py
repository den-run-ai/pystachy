# error: syntax_lambda_default_order.py:3: error: parameter without a default follows parameter with a default
def f(x):
    return lambda a=1, b: a


print("ran")
