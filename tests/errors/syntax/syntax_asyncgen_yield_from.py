# error: syntax_asyncgen_yield_from.py:5: error: 'yield from' inside async function
# Adapted from CPython 3.13.16 Lib/test/test_asyncgen.py (PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt), AsyncGenSyntaxTest.test_async_gen_syntax_02
async def foo():
    yield from 123
