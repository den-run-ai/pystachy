# Exception classes deriving from SystemExit: except SystemExit catches them, except Exception
# does not, and one nothing catches ends the program as SystemExit with its code would.
import sys


class Quit(SystemExit):
    pass


class Abort(Quit):
    def __init__(self, why: str, status: int):
        super().__init__(status)
        self.why = why


def run(n: int) -> None:
    try:
        if n == 0:
            raise Quit()
        if n == 1:
            raise Quit(3)
        if n == 2:
            raise Abort("disk", 4)
        if n == 3:
            raise Quit("message")
        if n == 4:
            raise Quit(True)
        raise Quit(1, 2)
    except Exception:
        print("never: SystemExit is no Exception")
    finally:
        print("finally", n)


for i in range(6):
    try:
        run(i)
    except Abort as e:
        print("abort:", e.why, repr(e), str(e))
    except SystemExit as e:
        print("exit:", repr(e), repr(str(e)))
try:
    sys.exit(Quit(5))
except SystemExit as e:
    print("sys.exit of one:", repr(e))
try:
    raise Abort("last", 6)
finally:
    print("on the way out")
