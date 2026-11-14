# error: syntax_asyncgen_return_await.py:7: error: 'return' with value in async generator
# Adapted from CPython 3.13.16 Lib/test/test_asyncgen.py (PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt), AsyncGenSyntaxTest.test_async_gen_syntax_03
async def foo():
    await abc
    yield
    return 123
