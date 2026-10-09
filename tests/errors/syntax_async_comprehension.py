# error: syntax_async_comprehension.py:3: error: asynchronous comprehension outside of an asynchronous function
def f(x):
    return [await y for y in x]


print("ran")
