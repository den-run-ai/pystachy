# error: expected int, got float
def branches(flag, integer, decimal):
    if flag:
        return [integer]
    return [decimal]


print(branches(True, 1, 2.5))
