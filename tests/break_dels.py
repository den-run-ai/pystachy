# A variable deleted on the way to one break of a while True loop is unbound after the loop,
# though it is assigned at the breaks before


def dels(x: int) -> int:
    while True:
        k = 5
        if x == 0:
            break
        del k
        if x == 1:
            break
        x -= 1
    return k


print(dels(0))
print(dels(3))
