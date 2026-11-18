# error: expected int, got float (compiling last(int, int) for the call at
# A function compiled for an int argument (#711) that calls itself before a return statement
# returns what its annotation says there, a float, which the int beside it does not join
def last(x: float, n: int) -> float:
    return x if n == 0 else last(x, n - 1)


print(last(3, 2))
