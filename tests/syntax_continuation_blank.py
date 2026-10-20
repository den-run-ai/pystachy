# A line that a backslash continues into a blank or comment line is blank, as in CPython's
# tokenizer: it neither indents nor ends a block, however far its backslash is indented.
def f() -> int:
    y = 1
    \

    \
    # a comment
    y += 1
        \

  \
# a comment
    return y


\

print(f())
