# error: closure_maybe_unassigned.py:5: error: f() reads 'y', which may not be assigned yet where it is defined: not supported (a function reads the variables around it when it runs: assign 'y' before the def)
def k(b: bool) -> int:
    if b:
        y = [1]
    def f() -> list[int]:
        return y
    try:
        print(len(f()))
    except NameError as e:
        print("NameError", e)
    return 1


print(k(False))
