# A field stored from a list comprehension is a list of its element's type, its variable being an
# item of its iterable, as mypy's FuncItem stores self.arg_names = [None if arg.pos_only else
# arg.variable.name for arg in self.arguments]: with None if c else v, of v's type or None, and
# attributes of attributes of an object (a field, or what a property returns), also self's.
class Var:
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name


class Argument:
    def __init__(self, variable: Var, pos_only: bool) -> None:
        self.variable = variable
        self.pos_only = pos_only


class FuncItem:
    def __init__(self, arguments: list[Argument], sizes: list[int]) -> None:
        self.arguments = arguments
        self.arg_names = [None if arg.pos_only else arg.variable.name for arg in self.arguments]
        self.flags = [arg.pos_only for arg in arguments]
        self.vars = [arg.variable for arg in arguments]
        self.doubled = [n * 2 for n in sizes]
        self.squares = [i * i for i in range(3)]
        self.label = None if len(sizes) == 0 else str(len(sizes))
        self.head = Argument(Var("h"), False)
        self.head_name = self.head.variable.name


f = FuncItem([Argument(Var("x"), True), Argument(Var("y"), False)], [1, 2])
print(f.arg_names, f.flags, [v.name for v in f.vars], f.doubled, f.squares, f.label, f.head_name)
f.arg_names.append("z")
f.arg_names.append(None)
print(f.arg_names, FuncItem([], []).label)
