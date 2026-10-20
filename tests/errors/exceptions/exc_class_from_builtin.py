# error: expected an object of E, got a builtin exception, which is not converted to a class of the program (catch it as one: except E as e)
class E(Exception):
    pass


def log(e: E) -> None:
    print("log", e)


try:
    raise E("x")
except Exception as e:
    log(e)
