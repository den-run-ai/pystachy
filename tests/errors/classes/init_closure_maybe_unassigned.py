# error: init_closure_maybe_unassigned.py:6: error: f() reads 'y', which may not be assigned yet where it is defined: not supported (a function reads the variables around it when it runs: assign 'y' before the def)
class K:
    def __init__(self, b: bool) -> None:
        if b:
            y = [1]
        def f() -> list[int]:
            return y
        try:
            print(len(f()))
        except NameError as e:
            print("NameError", e)
        self.x = 1


print(K(False).x)
