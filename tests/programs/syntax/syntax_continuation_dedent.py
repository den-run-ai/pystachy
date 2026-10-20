# A backslash that continues a line at its start is read with the line's indentation, as CPython's
# tokenizer reads it: the spaces of the line it continues into count too, unless the backslash
# follows spaces, whose column it then gives. So no dedent ends a block at such a backslash.
x = 0
if x:
    x = 1
\
    x = 2
print(x)
if x == 0:
    \
          z = 3
    print(z)
\
\
print("done")
