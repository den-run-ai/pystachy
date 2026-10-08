# parenthesized with items (Python 3.10+), and a parenthesized expression as one item
import os

a = "with_parenthesized_a_" + str(os.getpid())
b = "with_parenthesized_b_" + str(os.getpid())
with (open(a, "w") as f, open(b, "w") as g):
    f.write("x")
    g.write("y")
print(f.closed, g.closed)
with (open(a) as f,):
    print(f.read())
with (open(b)) as g:
    print(g.read())
with (
    open(a) as f,
    open(b) as g,
):
    print(f.read() + g.read())
os.remove(a)
os.remove(b)
