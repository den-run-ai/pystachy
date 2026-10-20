# error: hasattr_file_lookahead.py:7: error: hasattr() of 'read' on a TextIOWrapper is not supported
# The look-ahead from the print, for what the empty list holds, decides the if's test: its
# error names the if.
def g(f):
    xs = []
    print(xs)
    if hasattr(f, "read"):
        xs.append(1)
    print(xs)


g(open("hasattr_file_lookahead.py"))
