# A loop's break skips its else block: what the else block assigns does not narrow after the
# loop, so None raises CPython's error


def upper(x: str | None, n: int) -> str:
    for i in range(n):
        break
    else:
        x = "e"
    return x.upper()


print(upper(None, 0))
print(upper(None, 1))
