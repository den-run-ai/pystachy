# error: cannot iterate over int | str | tuple[int,str]
# A loop needs the member: narrow the value with isinstance(v, tuple) first (CPython prints 2, two)
def get(k: int) -> int | str | tuple[int, str]:
    if k == 0:
        return 1
    if k == 1:
        return "s"
    return (2, "two")


def main() -> None:
    v = get(2)
    for x in v:
        print(x)


main()
