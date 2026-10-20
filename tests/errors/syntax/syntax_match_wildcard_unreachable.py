# error: syntax_match_wildcard_unreachable.py:4: error: wildcard makes remaining patterns unreachable
def f(x):
    match x:
        case _ | 0:
            return 0


print("ran")
