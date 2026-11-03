# error: open() of a binary mode with buffering=1 is not supported (CPython warns that line buffering isn't supported in binary mode
f = open("x.bin", "rb", buffering=1)
