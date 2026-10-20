# error: lambda.py:3: error: the lambda reads 'y', which may not be assigned yet where it is defined: not supported (a function reads the variables around it when it runs: assign 'y' before the lambda)
def f(x):
    g = lambda: x + y
    y = 2
    return g()


print(f(1))
