class Row:
    cells: list[Cell]

    def width(self):
        return len(self.cells)


class Cell:
    pass
