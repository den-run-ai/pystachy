# error: syntax_generic_await.py:3: error: await expression cannot be used within the definition of a generic
async def f(x):
    class A[T]((await x)):
        pass
