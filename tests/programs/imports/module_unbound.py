# A module global that the module's code may leave unbound: reading it from another module
# raises AttributeError.
from scope import late

print(late.always)
print(late.payload)
