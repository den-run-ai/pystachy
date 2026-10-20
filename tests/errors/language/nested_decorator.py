# error: too many statically nested blocks
# a decorator is evaluated where the def statement is (the function is never called)
def deco(x):
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
                                                                                    for i20 in range(1):
                                                                                        @x[[a for a in x][0]]
                                                                                        def h():
                                                                                            pass


print("ok")
