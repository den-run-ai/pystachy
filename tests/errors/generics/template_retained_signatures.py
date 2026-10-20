# error: retained template signatures exceed 16777216 bytes, f11() keeping the most
# Under every other limit, each level doubles the instances that keep x12's 45,048-byte type:
# 4,095 of them would retain 184 MB (#179's reproducer).
x0 = 1
x1 = (x0, x0)
x2 = (x1, x1)
x3 = (x2, x2)
x4 = (x3, x3)
x5 = (x4, x4)
x6 = (x5, x5)
x7 = (x6, x6)
x8 = (x7, x7)
x9 = (x8, x8)
x10 = (x9, x9)
x11 = (x10, x10)
x12 = (x11, x11)
def f0(x, choose: bool) -> int:
    if choose:
        return f1((x, 1), choose)
    return f1((x, ""), choose)
def f1(x, choose: bool) -> int:
    if choose:
        return f2((x, 1), choose)
    return f2((x, ""), choose)
def f2(x, choose: bool) -> int:
    if choose:
        return f3((x, 1), choose)
    return f3((x, ""), choose)
def f3(x, choose: bool) -> int:
    if choose:
        return f4((x, 1), choose)
    return f4((x, ""), choose)
def f4(x, choose: bool) -> int:
    if choose:
        return f5((x, 1), choose)
    return f5((x, ""), choose)
def f5(x, choose: bool) -> int:
    if choose:
        return f6((x, 1), choose)
    return f6((x, ""), choose)
def f6(x, choose: bool) -> int:
    if choose:
        return f7((x, 1), choose)
    return f7((x, ""), choose)
def f7(x, choose: bool) -> int:
    if choose:
        return f8((x, 1), choose)
    return f8((x, ""), choose)
def f8(x, choose: bool) -> int:
    if choose:
        return f9((x, 1), choose)
    return f9((x, ""), choose)
def f9(x, choose: bool) -> int:
    if choose:
        return f10((x, 1), choose)
    return f10((x, ""), choose)
def f10(x, choose: bool) -> int:
    if choose:
        return f11((x, 1), choose)
    return f11((x, ""), choose)
def f11(x, choose: bool) -> int:
    return 1
print(f0(x12, True))
