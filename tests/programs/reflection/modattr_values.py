# attributes and methods of module values (sys.stdout.name.upper()); files compare by identity
import sys
from sys import stdout

print(sys.stdout.name.upper(), sys.stdin.name.strip("<>"), sys.stdout.mode.upper(), stdout.name.upper())
print(sys.stdout == sys.stdout, sys.stdout != sys.stderr, sys.stdout is sys.stdout, stdout == sys.stdout)
print(len(sys.argv[0]) > 0, sys.argv[1:], len(sys.argv))
