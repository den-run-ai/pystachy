# Where CPython counts blocks toward its limit of 21: an annotation in a function's body is
# not compiled, a generic function's annotations and a generic class's bases are evaluated in
# a scope of their own, a lambda's default values outside it, and a generator function's body
# is in a block. None of these templates is called, so the limit alone decides whether the
# program compiles
def annotated(x):
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
                                                                                        y: [a for a in x] = x


def generic(x):
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
                                                                                        def h[T](p: [a for a in x]) -> [b for b in x]:
                                                                                            pass
                                                                                        class C[T]([a for a in x][0]):
                                                                                            pass


def defaults(x):
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
                                                                                    f = lambda q=[a for a in x]: q


def generator(x):
    yield x
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
                                                                                    pass


print("ok")
