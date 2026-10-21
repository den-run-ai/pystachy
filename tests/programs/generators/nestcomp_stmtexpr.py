# A function compiled in the middle of another's compile leaves that compile as it was (#822):
# make_gen(int) is compiled for the receiver of make_gen(3).close(), an expression statement,
# which close() still is after make_gen's own statements are compiled.
def make_gen(n):
    print("start", n)
    for i in range(n):
        yield i


make_gen(3).close()
print("ok")
