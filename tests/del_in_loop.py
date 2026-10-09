# A variable deleted in a loop body is unbound in the next pass.
def f() -> None:
    x = "val"
    for i in range(2):
        print(x.upper())
        del x


f()
