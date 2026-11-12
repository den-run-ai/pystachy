# error: syntax_asyncgen_yield_from_await.py:6: error: 'yield from' inside async function
# Adapted from CPython 3.13.16 Lib/test/test_asyncgen.py (PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt), AsyncGenSyntaxTest.test_async_gen_syntax_01
async def foo():
    await abc
    yield from 123
