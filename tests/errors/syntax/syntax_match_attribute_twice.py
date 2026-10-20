# error: syntax_match_attribute_twice.py:4: error: attribute name repeated in class pattern: a
def f(x):
    match x:
        case P(a=1, a=2):
            return 1


print("ran")
