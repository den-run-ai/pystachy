# error: 'yield' is not supported (there are no generator functions): __iter__ can return iter(xs) of a list xs of the items
from emods.lines import Lines

ls = Lines("a\nb")
print(ls.count())
print("a" in ls)
