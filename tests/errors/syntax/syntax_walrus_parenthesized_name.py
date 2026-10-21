# error: syntax_walrus_parenthesized_name.py:3: error: cannot use assignment expressions with name
def f(x):
    return ((x) := 1)


print("ran")
