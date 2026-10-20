# error: 'value' is None here, and giving it a str inside an if branch or a loop is not supported
def conditional(value, flag: bool) -> None:
    print((value := "bound") if flag else "else")
    print(value)


conditional(None, False)
