# A function compiled in the middle of another's compile leaves that compile as it was (#822):
# here make(int), whose own comparison n > 2 is compiled while dry() types x = make(3) for f's
# read in x is None, which then is still the operand of that comparison.
def make(n):
    if n > 2:
        print("big")
    return None


def f():
    x = None
    if x is None:
        print("x is None")
    x = make(3)
    if x is None:
        print("still None")


f()
