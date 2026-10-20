# error: syntax_match_key_fstring.py:4: error: mapping pattern keys may only match literals and attribute lookups
def f(x):
    match x:
        case {f"k": a}:
            return a


print("ran")
