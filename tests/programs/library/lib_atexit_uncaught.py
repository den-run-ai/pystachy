# atexit's callbacks where an exception that nothing catches ends the program: its message first,
# then the callbacks; the status stays 1
import atexit


def catches() -> None:
    try:
        raise ValueError("in callback")
    except ValueError as error:
        print(str(error))


atexit.register(catches)
atexit.register(print, "bye")
raise KeyError("k")
