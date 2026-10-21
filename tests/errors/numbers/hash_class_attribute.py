# error: hash_class_attribute.py:8: error: class attribute __hash__ of NoHash is not supported where its objects are hashed
# (CPython: TypeError: unhashable type: 'NoHash'; a __hash__ that is no method is not one Pystachy
# can call, nor identity's)
class NoHash:
    __hash__: int | None = None


seen = {NoHash()}
