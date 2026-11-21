# atexit's callbacks where an exception that nothing catches ends the program: its message first,
# then the callbacks; the status stays 1
import atexit


def fail() -> None:
    raise ValueError("in callback")


def catches() -> None:
    try:
        fail()
    except ValueError as error:
        print(str(error))


atexit.register(catches)
atexit.register(print, "bye")
raise KeyError("k")
