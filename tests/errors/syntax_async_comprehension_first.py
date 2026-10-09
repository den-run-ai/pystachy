# error: syntax_async_comprehension_first.py:4: error: asynchronous comprehension outside of an asynchronous function
# CPython's compiler checks the comprehension before the await in it
def f(x):
    return [y for y in x
            if await y]
