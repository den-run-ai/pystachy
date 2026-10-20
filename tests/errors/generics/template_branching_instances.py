# error: template_branching_instances.py:7: error: compilation needs more than 4096 template specializations
# Each function calls the next with two short types: f0 and the 4,095 instances under its first
# call reach the limit, and its second call needs the 4,097th (#101).
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
    if choose:
        return f12((x, 1), choose)
    return f12((x, ""), choose)
def f12(x, choose: bool) -> int:
    return 1
print(f0(0, True))
