# error: reading '__doc__' in a class body is not supported (a class's docstring cannot be read)
# A class body's __doc__ is its docstring, which Pystachy cannot read (a function's reads the
# module's)
class Note:
    """A note."""
    text: str = __doc__


print(Note.text)
