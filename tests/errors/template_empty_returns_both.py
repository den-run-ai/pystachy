# error: pick() returns both list and int (each function has one return type)
def pick(flag):
    out = []
    if flag:
        return out
    return 5


print(pick(True))
