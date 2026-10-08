# empty [] and {} take their type from a module-level variable a function assigns through
gs: dict[str, list[int]] = {}


class Reg:
    def __init__(self):
        self.items: dict[str, list[str]] = {}
        self.names: list[str] = ["x"]


reg = Reg()
grid: list[list[int]] = [[1], [2]]


def add(k: str) -> None:
    gs[k] = []
    gs[k].append(1)
    reg.items[k] = []
    reg.items[k].append("v")
    reg.names = []
    grid[0] = []


add("a")
add("b")
print(gs, reg.items, reg.names, grid)
