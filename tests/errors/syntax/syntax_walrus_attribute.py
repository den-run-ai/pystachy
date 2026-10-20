# error: syntax_walrus_attribute.py:3: error: cannot use assignment expressions with attribute
def f(x):
    return (x.y := 1)


print("ran")
