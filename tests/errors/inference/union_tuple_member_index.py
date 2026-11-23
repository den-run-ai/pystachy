# error: 'int | str | tuple[int,str]' object is not subscriptable
# An index needs the member: narrow the value with isinstance(v, tuple) first (CPython prints 2)
def get(k: int) -> int | str | tuple[int, str]:
    if k == 0:
        return 1
    if k == 1:
        return "s"
    return (2, "two")


def main() -> None:
    v = get(2)
    print(v[0])


main()
