# A template whose function always raises (or exits) can be called where a value is expected:
# its call takes the type the context expects, and the code after it is never reached.
import sys
def fail(msg):
    raise ValueError(msg)
def bad(x):
    fail("bad " + str(x))
def stop(code):
    print("stopping")
    sys.exit(code)
def parse(s: str) -> int:
    if s.isdigit():
        return int(s)
    return fail("bad " + s)
def half(n: int) -> float:
    if n % 2 == 0:
        return n / 2
    return bad(n)
for s in ["12", "zz"]:
    try:
        print(parse(s))
    except ValueError as e:
        print("caught", e)
try:
    x = 1 + fail("t03")
except ValueError as e:
    print("caught", e)
try:
    print(half(4), half(3))
except ValueError as e:
    print("caught", e)
ok: bool = True
try:
    ok = fail("b") or True
except ValueError:
    print(ok)
stop(3)
