# error: expected str, got int
def repeated[T](value: T):
    kept: T = value
    def repeated[T](other: T):
        result: T = 3
        return result
    return repeated("inner")


print(repeated(1))
