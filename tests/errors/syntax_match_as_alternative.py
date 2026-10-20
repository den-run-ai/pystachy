# error: syntax_match_as_alternative.py:4: error: invalid syntax
def f(x):
    match x:
        case (1 | 2) as w | (3 as w):
            return w


print("ran")
