# error: 'value' is None here, and giving it a str inside an if branch or a loop is not supported
def conditional(value, flag: bool) -> None:
    if flag or (lambda x=(value := "bound"): x)():
        pass
    print(value)


conditional(None, True)
