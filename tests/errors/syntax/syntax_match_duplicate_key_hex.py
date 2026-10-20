# error: syntax_match_duplicate_key_hex.py:5: error: mapping pattern checks duplicate key (18446744073709551616)
# Keys too big for 64 bits compare by value, also written in another base.
def f(x):
    match x:
        case {0x10000000000000000: a, 18446744073709551616: b}:
            return a


print("ran")
