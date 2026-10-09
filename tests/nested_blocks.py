# 21 statically nested blocks, CPython's limit: two with statements of two items, six while
# loops, ten for loops and a list comprehension
total = 0
with open("/dev/null") as f0, open("/dev/null") as g0:
    with open("/dev/null") as f1, open("/dev/null") as g1:
        while total < 1:
            total += 1
            while total < 2:
                total += 1
                while total < 3:
                    total += 1
                    while total < 4:
                        total += 1
                        while total < 5:
                            total += 1
                            while total < 6:
                                total += 1
                                for i0 in range(2):
                                    for i1 in range(2):
                                        for i2 in range(2):
                                            for i3 in range(2):
                                                for i4 in range(2):
                                                    for i5 in range(2):
                                                        for i6 in range(2):
                                                            for i7 in range(2):
                                                                for i8 in range(2):
                                                                    for i9 in range(2):
                                                                        total += sum([k for k in range(i9 + 1)])
print(total)
