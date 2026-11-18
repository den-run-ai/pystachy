# inspect.cleandoc(): the first line's leading spaces, the margin shared by the lines after it
# (tabs expanded), and blank lines at both ends
import inspect

docs = [
    "",
    "one line",
    "   leading",
    "first\n    second\n      third\n    fourth",
    "\n\n    after blank lines\n      indented\n\n    end\n\n  ",
    "first\n\tsecond tab\n\t\tthird tab",
    "first\n  two\n one\n   three",
    "   \n   \n",
    "a\n\n\n   b\n\n",
    "trailing spaces   \n   x  ",
    "tabs\tin\tfirst\n        eight\n\tone tab",
    "first\nno margin\n    indented",
    "\n",
    "x\n      \n  y\n",
    "café\n   naïve\n     日本",
]
for d in docs:
    print(repr(inspect.cleandoc(d)))


DOC = """Summary line.

        Indented further.
    Back at the margin.
    """
print(inspect.cleandoc("""
    Hello
      world
    """))
print(inspect.cleandoc(DOC))
print(inspect.cleandoc(DOC) == inspect.cleandoc(inspect.cleandoc(DOC)), inspect.cleandoc(inspect.__doc__ or "")[:52])
