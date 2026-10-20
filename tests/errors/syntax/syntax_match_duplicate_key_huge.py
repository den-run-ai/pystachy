# error: syntax_match_duplicate_key_huge.py:5: error: mapping pattern checks duplicate key (99999999999999999999)
# A key too big for 64 bits, twice.
def f(x):
    match x:
        case {99999999999999999999: a, 99999999999999999999: b}:
            return a


print("ran")
