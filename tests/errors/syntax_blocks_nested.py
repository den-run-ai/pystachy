# error: syntax_blocks_nested.py:27: error: too many statically nested blocks
# CPython's compiler allows 21 blocks open in a function: loops, with items, try bodies and
# except handlers (two each), finally blocks and inlined comprehensions
def f(x: list[int]) -> int:
    n = 0
    for i0 in x:
        for i1 in x:
            for i2 in x:
                for i3 in x:
                    for i4 in x:
                        for i5 in x:
                            for i6 in x:
                                for i7 in x:
                                    for i8 in x:
                                        for i9 in x:
                                            for i10 in x:
                                                for i11 in x:
                                                    for i12 in x:
                                                        for i13 in x:
                                                            for i14 in x:
                                                                for i15 in x:
                                                                    for i16 in x:
                                                                        for i17 in x:
                                                                            for i18 in x:
                                                                                for i19 in x:
                                                                                    for i20 in x:
                                                                                        n += len([y for y in x])
    return n
