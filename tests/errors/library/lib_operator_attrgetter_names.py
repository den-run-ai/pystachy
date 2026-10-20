# error: cannot iterate over tuple[str,int]: its items have different types
# attrgetter() tests each name in a loop, which takes items of one type; CPython raises
# TypeError: attribute name must be a string
from operator import attrgetter

g = attrgetter("a", 1)
