# error: cannot compare an exception == int
try:
    int("x")
except ValueError as e:
    print(e == 5)
