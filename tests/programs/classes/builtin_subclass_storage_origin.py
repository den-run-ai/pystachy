class Stack(list[int]):
    pass


original = [[1]]
alias = original


def run() -> None:
    original = [[99]]
    alias.append(Stack([2]))
    print(type(alias[1]).__name__, alias, original)


run()
