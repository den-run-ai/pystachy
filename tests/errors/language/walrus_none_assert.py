# error: 'value' is None here, and giving it a str inside an if branch or a loop is not supported
def conditional(value, flag: bool) -> None:
    assert flag, (value := "bound")
    print(value)


conditional(None, True)
