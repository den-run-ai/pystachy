# error: too many statically nested blocks
# a dict comprehension is a block, and its key is evaluated inside it (the function is never called)
def keys(x):
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
                                                                                    y = {[a for a in x][0]: 1 for q in x}


print("ok")
