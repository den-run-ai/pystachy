# error: 'value' is None here, and giving it a str inside an if branch or a loop is not supported
def conditional(value, n: int) -> None:
    print(0 < n < len(value := "bound"))
    print(value)


conditional(None, -1)
