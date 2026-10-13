class Result:
    def __init__(self, status: bool, value):
        self.status = status
        self.value = value


def digit(s):
    if s.isdigit():
        return Result(True, int(s))
    return Result(False, None)


def show() -> None:
    r = digit("7")
    print(r.status, r.value)


show()
