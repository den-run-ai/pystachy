# error: syntax_generator_argument_line.py:5: error: Generator expression must be parenthesized
# (the line of the generator expression)
def f(x):
    return g(1,
             y for y in x)


print("ran")
