# error: syntax_match_as_wildcard.py:4: error: cannot use '_' as a target
def f(x):
    match x:
        case [1] as _:
            return 1


print("ran")
