# error: init_lambda_maybe_unassigned.py:6: error: the lambda reads 'y', which may not be assigned yet where it is defined: not supported (a function reads the variables around it when it runs: assign 'y' before the lambda)
class K:
    def __init__(self, b: bool) -> None:
        if b:
            y = 1
        g = lambda: y + 1
        try:
            print(g())
        except NameError as e:
            print("NameError", e)
        self.x = 1


print(K(False).x)
