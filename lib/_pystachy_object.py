"""The object type of the builtins, as a class of the subset.

Pystachy's own module: object() makes an object of this class, as a sentinel (_MISSING = object())
is made, a new one at each call. Such an object has no attributes; ==, hash() and repr() are its
identity's (<object object at 0x...>), as object's own __eq__, __hash__ and __repr__ are, and
type(x).__name__ is "object". The compiler loads this module for a program that may call object()
(analysis.object_values, Loader.program); programs do not import it, it runs no code, and an
annotation of object still takes any type.
"""


class object:
    __slots__ = ()
