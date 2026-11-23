# An untaken conditional extension cannot change the type of an existing variable.
b = "caller"
from conditional_extra import *

print(b.upper())
