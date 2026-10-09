# error: syntax_global_used_and_assigned.py:5: error: name 'x' is used prior to global declaration
def f() -> None:
    x = 1
    print(x)
    global x


print("ran")
