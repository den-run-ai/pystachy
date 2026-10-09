# A variable deleted in a for or while loop's else block is unbound after the loop, unless a
# break skipped the else block (a while True loop never runs its else block)


def found(n: int) -> int:
    x = 1
    for i in range(n):
        if i == 1:
            break
    else:
        del x
    return x


def again(n: int) -> int:
    x = 1
    while n > 0:
        n -= 1
    else:
        del x
        x = 2
    return x


def ends(n: int) -> int:
    x = 1
    for i in range(n):
        if i == 2:
            break
    else:
        del x
        return 0
    return x


def forever(n: int) -> int:
    x = 1
    while True:
        n -= 1
        if n < 0:
            break
    else:
        del x
    return x


print(found(5))
print(again(3))
print(ends(5), ends(1))
print(forever(2))
print(found(1))
