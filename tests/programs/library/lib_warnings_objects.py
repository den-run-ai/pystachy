# warnings given warning objects, of a class of the program with an __init__ of its own and of a
# builtin class: an error filter raises the object itself, and a recorded message holds a warning
# of its class (lib/warnings.py's _as_exc())
import warnings


class AppWarning(UserWarning):
    def __init__(self, text: str, code: int = 3):
        super().__init__(text)
        self.code = code


w0 = AppWarning("x", 7)
b0 = UserWarning("b")
with warnings.catch_warnings():
    warnings.simplefilter("error")
    try:
        warnings.warn(w0)
    except AppWarning as e:
        print(e is w0, e.code, repr(e))
    try:
        warnings.warn(b0)
    except UserWarning as e:
        print(e is b0, repr(e))
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("always")
    warnings.warn(w0)
    warnings.warn(b0)
    print([(type(m.message).__name__, str(m.message), m.message is b0) for m in log])
