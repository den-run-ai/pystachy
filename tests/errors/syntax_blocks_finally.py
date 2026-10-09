# error: syntax_blocks_finally.py:29: error: too many statically nested blocks
# CPython compiles a finally block twice: where the try ends, and with one block more where an
# exception runs it; the error only the second finds (the first for loop) comes after the with
try:
    pass
finally:
    for i0 in range(1):
        for i1 in range(1):
            for i2 in range(1):
                for i3 in range(1):
                    for i4 in range(1):
                        for i5 in range(1):
                            for i6 in range(1):
                                for i7 in range(1):
                                    for i8 in range(1):
                                        for i9 in range(1):
                                            for i10 in range(1):
                                                for i11 in range(1):
                                                    for i12 in range(1):
                                                        for i13 in range(1):
                                                            for i14 in range(1):
                                                                for i15 in range(1):
                                                                    for i16 in range(1):
                                                                        for i17 in range(1):
                                                                            for i18 in range(1):
                                                                                for i19 in range(1):
                                                                                    for j in range(1):
                                                                                        pass
                                                                                    with open('a') as f, open('b') as g:
                                                                                        pass
print("never")
