# error: tuple index out of range: 5 for a tuple of 2 items (a constant index is checked at compile time)
try:
    t = (1, 2)
    print(t[5])
except IndexError as e:
    print("caught", e)
