# error: cannot infer the type of field 'rows'
# tuple(xs) of a list of lists is no runtime-length tuple, which holds no lists yet
class Table:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = tuple(rows)


print(len(Table([[1], [2]]).rows))
