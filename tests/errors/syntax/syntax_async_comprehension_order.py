# error: syntax_async_comprehension_order.py:6: error: 'break' outside loop
# an async comprehension is an error of CPython's compiler, which compiles g first
def g(x):
    for v in x:
        pass
    break


def f(y):
    return [v async for v in y]
