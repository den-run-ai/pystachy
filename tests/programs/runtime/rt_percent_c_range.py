# %c of an int outside range(0x110000) raises CPython's OverflowError, not chr()'s ValueError
def gi(flag: bool) -> int | None:
    if flag:
        return 1114112
    return None


print("[%c]" % 1114111 == "[" + chr(1114111) + "]", "%c" % 0 == chr(0))
print("%c" % gi(True))
