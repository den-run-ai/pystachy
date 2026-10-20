# sys.exit and raise SystemExit: finally blocks run, except SystemExit catches them (with the
# code's str and repr), except Exception does not; the last one ends the program with status 3
import sys


def leave(code: int) -> None:
    try:
        sys.exit(code)
    finally:
        print("finally of leave", code)


try:
    leave(4)
except SystemExit as e:
    print("caught", repr(e), "[" + str(e) + "]")
try:
    sys.exit()
except SystemExit as e:
    print("no code", repr(e), "[" + str(e) + "]")
try:
    sys.exit("message")
except SystemExit as e:
    print("message", repr(e), "[" + str(e) + "]")
try:
    raise SystemExit(True)
except BaseException as e:
    print("bool", repr(e), "[" + str(e) + "]")
try:
    raise SystemExit(1, 2)
except SystemExit as e:
    print("two", repr(e), "[" + str(e) + "]")
try:
    try:
        sys.exit(5)
    except Exception:
        print("not here")
except SystemExit as e:
    print("not an Exception", e)
try:
    print("start")
    leave(3)
except ValueError:
    print("not here either")
finally:
    print("last finally")
print("not reached")
