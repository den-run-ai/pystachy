# names this module's code leaves unbound: a try body that raised, an if that did not run,
# an except clause's name (deleted at its end)
try:
    x = int("nope")
except ValueError:
    pass
if len("ab") > 5:
    z = 3
try:
    raise KeyError("k")
except KeyError as w:
    pass
y = 2
