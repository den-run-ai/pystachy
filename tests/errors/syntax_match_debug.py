# error: syntax_match_debug.py:6: error: cannot assign to __debug__
def f(x):
    match x:
        case 0:
            return 0
        case __debug__:
            return 1


print("ran")
