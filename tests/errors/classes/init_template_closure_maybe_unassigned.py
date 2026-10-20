# error: init_template_closure_maybe_unassigned.py:6: error: f() reads 'y', which may not be assigned yet where it is defined: not supported (a function reads the variables around it when it runs: assign 'y' before the def) (compiling Box.__init__(int, bool) for the call at
class Box:
    def __init__(self, v, b: bool) -> None:
        if b:
            y = [v]
        def f():
            return y
        try:
            print(len(f()))
        except NameError as e:
            print("NameError", e)
        self.x = v


print(Box(1, False).x)
