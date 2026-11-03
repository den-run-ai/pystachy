# open() of a binary mode with arguments that binary files do not take (buffering=1, a buffering= that
# is no literal, closefd=, opener=, more than six arguments) is rejected only where the program reaches
# it (tests/errors/io/bfile_*): in code that is never compiled, such as an if False: block, it compiles,
# as it did before binary files
import sys

if False:
    open("nowhere", "rb", buffering=1)
    open("nowhere", "rb", buffering=len(sys.argv))
    open("nowhere", "rb", closefd=False)
    open("nowhere", "wb", opener=None)
    open("nowhere", "rb", -1, None, None, None, True)
print("compiled")
