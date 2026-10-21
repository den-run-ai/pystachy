# A with statement on a file object that is already closed raises ValueError as the file's
# __enter__ does, before its block runs.
import tempfile

p = tempfile.mkdtemp() + "/x"
f = open(p, "w")
with f:
    f.write("a")
print(f.closed)
try:
    with f:
        print("inside")
except ValueError as e:
    print("caught", e)
with open(p) as g:
    print(g.read())
print("after")
with g as h:
    print("never")
