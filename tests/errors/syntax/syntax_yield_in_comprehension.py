# error: syntax_yield_in_comprehension.py:3: error: 'yield' inside list comprehension
def f(x):
    return [(yield v) for v in x]


print("ran")
