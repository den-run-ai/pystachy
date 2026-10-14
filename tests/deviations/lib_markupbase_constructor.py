# The port declares base fields in __init__; its abstract class-object guard is omitted.
# CPython raises RuntimeError when ParserBase is constructed directly.
from _markupbase import ParserBase
print(ParserBase().getpos())
