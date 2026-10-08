# error: import * only allowed at module level
def f() -> int:
    from emods.mod import *
    return 1


print(f())
