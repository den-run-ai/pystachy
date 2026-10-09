# error: syntax_walrus_statement.py:4: error: invalid syntax
# := stands only in a condition, an argument, a subscript, a display's item, a comprehension
def f(x):
    y := x
    return y


print("ran")
