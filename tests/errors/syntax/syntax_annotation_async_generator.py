# error: syntax_annotation_async_generator.py:6: error: 'return' with value in async generator
# a yield in a local annotation, which CPython's compiler never compiles, makes g an async
# generator all the same
async def g(z):
    x: (yield from z) = 1
    return x
