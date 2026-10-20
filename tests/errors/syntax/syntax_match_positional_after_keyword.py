# error: syntax_match_positional_after_keyword.py:4: error: positional patterns follow keyword patterns
def f(x):
    match x:
        case P(a=1, b):
            return b


print("ran")
