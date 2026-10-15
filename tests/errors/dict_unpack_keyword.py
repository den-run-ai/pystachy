# error: dict displays with ** are not supported
def show(d: dict[str, str]) -> None:
    print(d)
show(d={**{"color": "red"}})
