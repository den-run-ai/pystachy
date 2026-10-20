# error: name 'emods.setter.done' is not defined yet here: a function assigns it, so declare it at module level in tests/emods/setter.py first (done: T)
from emods.setter import ready, done

ready()
print(done)
