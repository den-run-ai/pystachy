# error: syntax_match_name_twice.py:4: error: multiple assignments to name 'a' in pattern
def f(x):
    match x:
        case {"k": a, **a}:
            return a


print("ran")
