# error: syntax_async_for_outside_async.py:3: error: 'async for' outside async function
def f(x):
    async for y in x:
        pass


print("ran")
