# error: an async for clause of a comprehension over list is not supported: it is no asynchronous iterable (CPython raises TypeError)
# CPython raises TypeError: 'async for' requires an object with __aiter__ method, got list, as the
# comprehension runs; an async for statement raises it as CPython does
async def main() -> None:
    try:
        print([x async for x in [1, 2]])
    except TypeError as e:
        print(e)


main().send(None)
