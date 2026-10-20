# A global whose first assignment is a, b = ... (or a comprehension), read by a template's
# function before it runs, raises NameError there, as in CPython.
def show(x):
    return str(x) + str(SQUARES) + str(LO)


SQUARES = [i * i for i in range(3)]
print(show(1))
LO, HI = 1, 2
