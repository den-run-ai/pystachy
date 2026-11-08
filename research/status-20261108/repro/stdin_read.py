import sys

data = sys.stdin.read()
print("read", len(data), repr(data[:4]))
