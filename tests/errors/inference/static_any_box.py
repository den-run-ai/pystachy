# error: static_any_box.py:8: error: this module is marked '# pystachy: static', which holds no Any value: a value of type str would be boxed as one here
# pystachy: static
# A static module boxes nothing (docs/dynamic-any.md#static-modules): logging's arguments are
# Any values, so the format string would be boxed where it is passed. Without the marker this compiles and
# allocates the box.
import logging

logging.warning("%d items", 3)
