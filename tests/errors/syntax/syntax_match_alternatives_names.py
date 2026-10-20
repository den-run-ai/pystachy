# error: syntax_match_alternatives_names.py:4: error: alternative patterns bind different names
def f(x):
    match x:
        case [a] | (b, 1):
            return 1


print("ran")
