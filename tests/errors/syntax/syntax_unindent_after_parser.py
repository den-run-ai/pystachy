# error: syntax_unindent_after_parser.py:3: error: invalid syntax
# a bad unindent later in the file replaces no parser error (CPython raises no exception for it)
x = = 1
if x:
        y = 1
    z = 2
