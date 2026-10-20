# error: syntax_match_duplicate_key_big.py:4: error: mapping pattern checks duplicate key (100000000000000000000)
def f(x):
    match x:
        case {1e20: a, 100000000000000000000: b}:
            return a


print("ran")
