# pystachy: python-int
# A SystemExit subclass of an int | None of a module that opts in to promoting ints
# (docs/python-int.md): its status is the promoting int's value
class Quit(SystemExit):
    pass


def code(v: int) -> int | None:
    return v if v > 0 else None


try:
    raise Quit(code(-1))
except SystemExit as e:
    print("Quit", repr(e))
raise Quit(code(2 ** 70 // 2 ** 66))
