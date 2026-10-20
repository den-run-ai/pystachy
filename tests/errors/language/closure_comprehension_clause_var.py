# error: closure_comprehension_clause_var.py:3: error: the lambda reads 'y', a variable of the comprehension it is in: not supported
def table(rows: list[list[int]]):
    return [lambda: y for row in rows for y in row]


print(len(table([[1, 2]])))
