# error: is read before its first assignment
def f() -> None:
    for i in range(3):
        if i > 0:
            print(prev)
        prev = i
