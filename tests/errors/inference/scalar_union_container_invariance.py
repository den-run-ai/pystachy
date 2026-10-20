# error: expected list[int | str], got list[int]

def replace(values: list[int | str]) -> None:
    values[0] = "changed"

values = [1]
replace(values)
print(values[0] + 1)
