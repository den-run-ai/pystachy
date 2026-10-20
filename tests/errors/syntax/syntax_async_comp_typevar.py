# error: syntax_async_comp_typevar.py:6: error: asynchronous comprehension outside of an asynchronous function
# a type parameter's default is compiled as a function of its own, which is not a coroutine,
# also in an async def
async def fetch(urls: list[str]) -> int:
    return len(urls)
class Box[T = [u async for u in fetch]]:
    pass


print("never")
