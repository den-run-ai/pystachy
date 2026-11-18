# error: cannot import name 'entry_points' from 'importlib.metadata'
# (entry points name objects that CPython imports as the program runs)
from importlib.metadata import entry_points

print(entry_points())
