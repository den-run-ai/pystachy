# error: syntax_match_capture_unreachable.py:4: error: name capture 'n' makes remaining patterns unreachable
def f(x):
    match x:
        case n:
            return n
        case 0:
            return 0


print("ran")
