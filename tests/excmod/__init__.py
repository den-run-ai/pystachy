# A package that gives the exception class of its submodule its own name, as tomllib does:
# "Pretend this exception was created here."
from ._impl import Boom, Worse, boom

print("before", Boom.__module__)
Boom.__module__ = __name__
print("after", Boom.__module__)
