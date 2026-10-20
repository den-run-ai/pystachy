# error: min_key_none.py:6: error: comparing the keys of min() is not supported: its key function returns None
def show(x: int) -> None:
    print(x)


print(min([3, 1, 2], key=show))
