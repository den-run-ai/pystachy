# error: syntax_match_starred_subject.py:3: error: invalid syntax
def f(x):
    match *x:
        case [1]:
            return 1


print("ran")
