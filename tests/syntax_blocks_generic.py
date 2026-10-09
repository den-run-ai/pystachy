# CPython's compiler counts the blocks of what a generic def or class or a type statement
# evaluates in a scope of its own (a type parameter's bound or default, a type alias's value, a
# generic def's annotations and a generic class's bases) from none: 20 loops around them do not
# make the comprehensions in them the 21st and 22nd block. In a class body, such a scope does
# not inline the comprehensions in it (they can see the class's names): each is a function of
# its own, so 22 of them nest there, where 21 is the limit elsewhere
def never(xs):  # (a template that no call compiles)
    for i0 in xs:
        for i1 in xs:
            for i2 in xs:
                for i3 in xs:
                    for i4 in xs:
                        for i5 in xs:
                            for i6 in xs:
                                for i7 in xs:
                                    for i8 in xs:
                                        for i9 in xs:
                                            for i10 in xs:
                                                for i11 in xs:
                                                    for i12 in xs:
                                                        for i13 in xs:
                                                            for i14 in xs:
                                                                for i15 in xs:
                                                                    for i16 in xs:
                                                                        for i17 in xs:
                                                                            for i18 in xs:
                                                                                for i19 in xs:
                                                                                    type A = [[0 for a in xs] for b in xs]

                                                                                    def f[T: [[0 for a in xs] for b in xs]](x: [[T for a in xs] for b in xs], y: [[0 for a in xs] for b in xs]) -> int:
                                                                                        return 0

                                                                                    class C[T = [[0 for a in xs] for b in xs]]([[0 for a in xs] for b in xs] and object):
                                                                                        pass

    class K:
        type Deep = [[[[[[[[[[[[[[[[[[[[[[0 for x0 in xs] for x1 in xs] for x2 in xs] for x3 in xs] for x4 in xs] for x5 in xs] for x6 in xs] for x7 in xs] for x8 in xs] for x9 in xs] for x10 in xs] for x11 in xs] for x12 in xs] for x13 in xs] for x14 in xs] for x15 in xs] for x16 in xs] for x17 in xs] for x18 in xs] for x19 in xs] for x20 in xs] for x21 in xs]

        def m[T](self, x: [[[[[[[[[[[[[[[[[[[[[[0 for x0 in xs] for x1 in xs] for x2 in xs] for x3 in xs] for x4 in xs] for x5 in xs] for x6 in xs] for x7 in xs] for x8 in xs] for x9 in xs] for x10 in xs] for x11 in xs] for x12 in xs] for x13 in xs] for x14 in xs] for x15 in xs] for x16 in xs] for x17 in xs] for x18 in xs] for x19 in xs] for x20 in xs] for x21 in xs]) -> int:
            return 0


print("ok")
