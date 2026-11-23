# error: a closed union holds one tuple type: isinstance() cannot tell two apart
def pick(k: int) -> tuple[int, int] | tuple[str, str] | int:
    if k == 0:
        return (1, 2)
    return 3


print(pick(0))
