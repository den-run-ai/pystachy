# error: field 'note' is outside __slots__ of 'object'
# an object of the builtins' object type has no attributes (CPython's AttributeError)
_MISSING = object()
_MISSING.note = "x"
print(_MISSING)
