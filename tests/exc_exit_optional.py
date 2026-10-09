# sys.exit() and SystemExit with a code that may be None (int | None, bool | None, str | None),
# in a program that has a try: None is status 0 (sys.exit(None) is SystemExit(), but
# SystemExit(None) keeps its None), an int the status, a bool its int, a str a message; the
# same through a class deriving from SystemExit. Uncaught at the end: status 3.
import sys


class Quit(SystemExit):
    pass


class Stop(SystemExit):
    def __init__(self, code: int | None) -> None:
        super().__init__(code)
        self.why = "stop"


def pick(i: int) -> int | None:
    return None if i == 0 else i


def pickb(i: int) -> bool | None:
    return None if i == 0 else i == 1


def picks(i: int) -> str | None:
    return None if i == 0 else "msg" + str(i)


def show(e: SystemExit) -> None:
    print(repr(e), repr(str(e)))


for i in range(3):
    c = pick(i)
    b = pickb(i)
    s = picks(i)
    try:
        sys.exit(c)
    except SystemExit as e:
        show(e)
    try:
        raise SystemExit(c)
    except SystemExit as e:
        show(e)
    try:
        sys.exit(b)
    except SystemExit as e:
        show(e)
    try:
        sys.exit(s)
    except SystemExit as e:
        show(e)
    try:
        raise Quit(c)
    except SystemExit as e:
        print(type(e).__name__, str(e), repr(e))
    try:
        raise Stop(c)
    except Stop as e:
        print(type(e).__name__, str(e), repr(e), e.why)
    try:
        try:
            sys.exit(c)
        finally:
            print("finally", i)
    except SystemExit:
        print("caught", i)
c3 = pick(3)
try:
    pass
finally:
    pass
raise Quit(c3)
