# A module global given an int by module code and floats by a function: int | float.
count = 0


def add(v: float) -> None:
    global count
    count = count + v


print(count)
add(1.5)
add(2.0)
print(count)
