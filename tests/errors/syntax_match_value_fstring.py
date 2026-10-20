# error: syntax_match_value_fstring.py:4: error: patterns may only match literals and attribute lookups
def f(x):
    match x:
        case f"a":
            return 1


print("ran")
