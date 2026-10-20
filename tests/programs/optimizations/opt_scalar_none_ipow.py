# int | None **= int with None: CPython's TypeError names the augmented operator alone
def gi(flag: bool) -> int | None:
    return 3 if flag else None


b = gi(False)
b **= 2
print(b)
