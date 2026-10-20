# Replacement fields as CPython 3.12 reads them: a comment runs to the end of its line and is
# left out of a self-documenting field's text (an "=" in it makes no "=" field), and white space,
# newlines and comments may come between a conversion and the ':' or '}' after it
x = "hi"
y = 7
w = 4
print(f"{x # note: a=
}")
print(f"{y # c
=}|")
print(f"{y # c=
:>4}|")
print(f"{y = # c
}|")
print(f"{y!r
}|")
print(f"{y!r :>4}|")
print(f"{y!s # c
:>{w}}|")
print(f"{y = !r # c
:>4}|")
print(f"{'#' # c
= }")
print(f"""{y # a=
}""")
print(f"{y:{'>':{''}}{w}}|")
