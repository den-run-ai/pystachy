# error: expected int, got str
def f() -> None:
    items = [1]
    items = ["x"]
    print(items)
f()
