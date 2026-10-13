# unions in fields, template arguments, nested containers, dict.get, while loops and early exits
class Cell:
    def __init__(self, v: int | str | None) -> None:
        self.v = v

    def show(self) -> str:
        v = self.v
        if v is None:
            return "empty"
        if isinstance(v, int):
            return f"#{v}"
        return v.upper()


cells = [Cell(1), Cell("ab"), Cell(None)]
print([c.show() for c in cells], cells[0].v, cells[2].v)
cells[2].v = 7
print(cells[2].show(), cells[2].v == 7)


def twice(x):
    return [x, x]


def unbox(x: int | str) -> str:
    if isinstance(x, str):
        return x
    return str(x)


u: int | str = "q"
print(twice(u), twice(3), [unbox(y) for y in twice(u)])
grid: list[list[int | str]] = [[1, "a"], ["b", 2]]
print(grid, grid[1][0], len(grid[0]))
table: dict[str, int | None | str] = {"a": 1, "b": None, "c": "x"}
print(table, table.get("a"), table.get("z"), table.get("b"), "c" in table)


def countdown(n: int | str) -> str:
    out = ""
    while isinstance(n, int) and n > 0:
        out += str(n)
        n = n - 1
    return out


def first_str(xs: list[int | str]) -> str:
    for x in xs:
        if not isinstance(x, str):
            continue
        return x
    return "none"


print(countdown(3), countdown("x"), first_str([1, 2, "z", "w"]), first_str([1]))
pairs: list[tuple[int, str] | str] = [(1, "a"), "b"]
print(pairs, pairs[0] == (1, "a"), pairs[1] != "b")
