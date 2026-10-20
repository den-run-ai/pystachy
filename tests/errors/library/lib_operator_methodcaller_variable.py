# error: getattr() of a name only the run time knows is supported where its text is used
# A method's name must be a constant: a getter specializes on literal arguments only, and calling a run-time name's attribute needs its value (#487, #489)
from operator import methodcaller

name = "upper"
print(methodcaller(name)("x"))
