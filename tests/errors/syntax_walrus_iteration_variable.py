# error: syntax_walrus_iteration_variable.py:3: error: assignment expression cannot rebind comprehension iteration variable 'y'
def f(x):
    return [y for y in x if (y := 1)]


print("ran")
