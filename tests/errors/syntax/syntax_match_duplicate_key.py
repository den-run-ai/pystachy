# error: syntax_match_duplicate_key.py:4: error: mapping pattern checks duplicate key (1.0)
def f(x):
    match x:
        case {True: a, 1.0: b}:
            return a


print("ran")
