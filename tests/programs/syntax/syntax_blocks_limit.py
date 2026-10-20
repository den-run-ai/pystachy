# 21 statically nested blocks are allowed (CPython's CO_MAXBLOCKS): loops, with items, and
# an inlined comprehension each count one; if statements and generator expressions none
n = 0
for i0 in range(2 if 0 == 0 else 1):
    for i1 in range(2 if 1 == 0 else 1):
        for i2 in range(2 if 2 == 0 else 1):
            for i3 in range(2 if 3 == 0 else 1):
                for i4 in range(2 if 4 == 0 else 1):
                    for i5 in range(2 if 5 == 0 else 1):
                        for i6 in range(2 if 6 == 0 else 1):
                            for i7 in range(2 if 7 == 0 else 1):
                                for i8 in range(2 if 8 == 0 else 1):
                                    for i9 in range(2 if 9 == 0 else 1):
                                        for i10 in range(2 if 10 == 0 else 1):
                                            for i11 in range(2 if 11 == 0 else 1):
                                                for i12 in range(2 if 12 == 0 else 1):
                                                    for i13 in range(2 if 13 == 0 else 1):
                                                        for i14 in range(2 if 14 == 0 else 1):
                                                            for i15 in range(2 if 15 == 0 else 1):
                                                                for i16 in range(2 if 16 == 0 else 1):
                                                                    for i17 in range(2 if 17 == 0 else 1):
                                                                        for i18 in range(2 if 18 == 0 else 1):
                                                                            for i19 in range(2 if 19 == 0 else 1):
                                                                                n += len([y for y in range(3) if y > 0])
                                                                                if n > 0:
                                                                                    n += sum(z for z in range(2))
print(n)
with open("/dev/null") as f0, open("/dev/null") as f1, open("/dev/null") as f2, open("/dev/null") as f3, open("/dev/null") as f4, open("/dev/null") as f5, open("/dev/null") as f6, open("/dev/null") as f7, open("/dev/null") as f8, open("/dev/null") as f9, open("/dev/null") as f10, open("/dev/null") as f11, open("/dev/null") as f12, open("/dev/null") as f13, open("/dev/null") as f14, open("/dev/null") as f15, open("/dev/null") as f16, open("/dev/null") as f17, open("/dev/null") as f18, open("/dev/null") as f19, open("/dev/null") as f20:
    print(f0.closed, f20.closed)
