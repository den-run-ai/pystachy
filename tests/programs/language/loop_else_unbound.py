# A variable assigned only in a loop's else block is unbound after a break.
def f(n: int) -> None:
    for i in range(n):
        if i == 1:
            break
    else:
        z = 1
    print(z)


f(0)
f(3)
