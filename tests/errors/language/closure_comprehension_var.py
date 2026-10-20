# error: closure_comprehension_var.py:3: error: the lambda reads 'x', a variable of the comprehension it is in: not supported
def table(xs):
    return [lambda: x for x in xs]


print(len(table([1, 2])))
