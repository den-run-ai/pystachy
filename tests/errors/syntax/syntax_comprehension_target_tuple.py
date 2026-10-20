# error: syntax_comprehension_target_tuple.py:3: error: did you forget parentheses around the comprehension target?
def f(x):
    return [a, b for a, b in x]


print("ran")
