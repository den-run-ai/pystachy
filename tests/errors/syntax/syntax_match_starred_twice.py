# error: syntax_match_starred_twice.py:4: error: multiple starred names in sequence pattern
def f(x):
    match x:
        case [a, *b, *c]:
            return a


print("ran")
