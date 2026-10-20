# sys.exit(code) of a str | None that is None, through a finally block, in a program that has
# a try: status 0 and nothing on stderr, as for sys.exit(None)
import sys

msg: str | None = "bad" if len(sys.argv) > 5 else None
try:
    print("body")
finally:
    print("finally")
    sys.exit(msg)
