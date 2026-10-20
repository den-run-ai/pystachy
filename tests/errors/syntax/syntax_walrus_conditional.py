# error: syntax_walrus_conditional.py:3: error: cannot use assignment expressions with conditional expression
def f(a, b, c):
    return (a if b else c := 1)


print("ran")
