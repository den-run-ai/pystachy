# error: except ... as msg is not supported here: the module's global 'msg' has another type, so the clause binds a variable of its own, which show() would not see
msg = "none"


def show() -> str:
    return "seen: " + str(msg)


try:
    raise ValueError("boom")
except ValueError as msg:
    print(show())
