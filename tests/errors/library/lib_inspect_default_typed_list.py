# error: a list[str] cannot become an Any value: its items are typed, and Any's containers hold Any items
# A default that is an existing list of typed items, but ints, cannot become the module's Any
# value, which would share the list; a list display given as the default can
import inspect

names = ["a"]
names.append("b")
print(inspect.Parameter("names", inspect.Parameter.KEYWORD_ONLY, default=names))
