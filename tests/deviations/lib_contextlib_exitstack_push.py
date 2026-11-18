# Documented deviation: ExitStack.push() of an object whose class defines both __call__() and
# __exit__() registers the call of the object. CPython registers its __exit__().
from contextlib import ExitStack


class Both:
    def __call__(self, t, v, tb) -> bool:
        print("called")
        return False

    def __enter__(self) -> "Both":
        return self

    def __exit__(self, t, v, tb) -> bool:
        print("exited")
        return False


with ExitStack() as stack:
    stack.push(Both())
