# error: syntax_match_rest_first.py:4: error: invalid syntax
def f(x):
    match x:
        case {**rest, "k": v}:
            return v


print("ran")
