# sys.exit() of a str | None that is None ends the program with status 0, as sys.exit(None)
import sys

x: str | None = None
print("before")
sys.exit(x)
