# error: expected tuple[list[int | str],float], got tuple[list[int | str],int]
def fresh(n):
    return ([n, "x"], 1)


result: tuple[list[int | str], float] = fresh(1)
