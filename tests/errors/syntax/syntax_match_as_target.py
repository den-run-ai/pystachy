# error: syntax_match_as_target.py:4: error: invalid pattern target
def f(x):
    match x:
        case [1] as (y):
            return y


print("ran")
