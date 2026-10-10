# A with-file's close failure replaces SystemExit, even without a try anywhere in the program.
import sys

with open("/dev/full", "w") as f:
    f.write("lost")
    sys.exit(0)
