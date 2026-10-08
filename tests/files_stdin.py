# sys.stdin as a file next to input(); sys.argv is a list the program can change; os.system
# does not flush stdout first (CPython does not either).
import os
import sys

first = input()
print("first:", first)
line = sys.stdin.readline()
print("line:", repr(line))
n = 0
for s in sys.stdin:
    n += 1
    print(n, repr(s))
    if n == 2:
        break
print("rest:", repr(sys.stdin.read()), sys.stdin.closed)
sys.argv.append("extra")
print(sys.argv[1:], sys.argv[0].endswith("files_stdin.py") or sys.argv[0].endswith(".exe"))
print("before")
os.system("echo child")
err = sys.stderr
err.write("to stderr\n")
