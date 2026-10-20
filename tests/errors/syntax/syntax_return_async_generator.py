# error: syntax_return_async_generator.py:4: error: 'return' with value in async generator
async def f():
    yield 1
    return 2


print("ran")
