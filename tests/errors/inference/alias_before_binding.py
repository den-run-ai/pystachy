# error: name 'plus' is used before 'plus = add' binds it
def add(a: int, b: int) -> int:
    return a + b


print(plus(1, 2))
plus = add
