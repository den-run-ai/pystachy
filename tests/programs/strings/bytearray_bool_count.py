# bytearray() of a bool holds as many zero bytes as the bool's int, as CPython makes it (#1552):
# True and False, a comparison's result and a bool parameter
def zeros(flag: bool) -> bytearray:
    return bytearray(flag)


b = bytearray(True)
print(b, bytearray(False), len(b), len(bytearray(False)))
b[0] = 7
b.append(65)
print(b)
print(zeros(3 > 2), zeros(3 < 2), zeros(not False) + bytearray(2))
