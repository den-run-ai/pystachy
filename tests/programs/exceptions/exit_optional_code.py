# sys.exit() and SystemExit of a code decided at run time: a value that may be None (sys.exit's
# None is status 0 and SystemExit(None), raised or made first, shows its None) and a tuple,
# whose items sys.exit() passes as SystemExit's arguments, so that sys.exit((3,)) is sys.exit(3);
# the last one is not caught.
import sys


def code(n: int) -> int | None:
    return None if n == 0 else n


for n in [0, 3]:
    try:
        sys.exit(code(n))
    except SystemExit as e:
        print("sys.exit:", repr(e), repr(str(e)))
    try:
        raise SystemExit(code(n))
    except SystemExit as e:
        print("SystemExit:", repr(e), repr(str(e)))
    try:
        sys.exit((code(n),))
    except SystemExit as e:
        print("sys.exit((code,)):", repr(e), repr(str(e)))
    made = SystemExit(code(n))  # (made first, raised later)
    print("made:", repr(made), repr(str(made)))
    try:
        raise made
    except SystemExit as e:
        print("raised:", repr(e))
try:
    sys.exit(())
except SystemExit as e:
    print("sys.exit(()):", repr(e), repr(str(e)))
try:
    sys.exit((1, "x"))
except SystemExit as e:
    print("sys.exit((1, 'x')):", repr(e), repr(str(e)))
try:
    raise SystemExit((1, "x"))
except SystemExit as e:
    print("SystemExit((1, 'x')):", repr(e), repr(str(e)))
print("exiting", flush=True)
sys.exit((code(4),))
