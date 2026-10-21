# error: type representation exceeds 65536 bytes
# Check the result size before constructing a billion tuple items in the compiler.
x = (1,) * 1000000000
