# error: cannot infer the type of class attribute 'SHOW'; annotate it (SHOW: T = ...)
# A method read through its class is no class attribute its body binds.
class Branch:
    BOOL = 100

    def show(self) -> str:
        return "branch"


class Printer:
    SHOW = Branch.show


print(Printer.SHOW(Branch()))
