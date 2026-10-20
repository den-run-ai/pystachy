# repr() of the AssertionError an assert raises, and of the SystemExit sys.exit() and raise
# SystemExit(code) raise, shows the repr of the message or code, whatever its type; str() and an
# uncaught SystemExit show its str().
import sys


class P:
    def __repr__(self) -> str:
        return "P()"

    def __str__(self) -> str:
        return "p-str"


for m in [3, -1]:
    try:
        assert m > 5, m
    except AssertionError as e:
        print(repr(e), str(e))
try:
    assert False, [1, 2]
except AssertionError as e:
    print(repr(e))
try:
    assert False, None
except AssertionError as e:
    print(repr(e), str(e))
try:
    assert 1 > 2, P()
except AssertionError as e:
    print(repr(e), str(e))
try:
    assert 1 > 2, "text"
except AssertionError as e:
    print(repr(e), str(e))
try:
    sys.exit(2.5)
except SystemExit as e:
    print(repr(e), str(e))
try:
    sys.exit([1, 2])
except SystemExit as e:
    print(repr(e))
try:
    raise SystemExit(P())
except SystemExit as e:
    print(repr(e), str(e))
try:
    raise SystemExit("s")
except SystemExit as e:
    print(repr(e), str(e))
sys.exit(1.5)
