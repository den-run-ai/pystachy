# error: syntax_blocks_async_comp.py:24: error: too many statically nested blocks
# a list comprehension's async for clause opens a block of its own in CPython's compiler, and
# a coroutine starts with one: 19 loops around [x async for x in b] make 22
async def h(b):
    for i0 in b:
        for i1 in b:
            for i2 in b:
                for i3 in b:
                    for i4 in b:
                        for i5 in b:
                            for i6 in b:
                                for i7 in b:
                                    for i8 in b:
                                        for i9 in b:
                                            for i10 in b:
                                                for i11 in b:
                                                    for i12 in b:
                                                        for i13 in b:
                                                            for i14 in b:
                                                                for i15 in b:
                                                                    for i16 in b:
                                                                        for i17 in b:
                                                                            for i18 in b:
                                                                                return [x async for x in b]


print("never")
