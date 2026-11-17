# error: 'LacksExit' object has no method '__exit__'
# ExitStack.enter_context() calls the manager's __enter__() and __exit__(), which its class must
# define: CPython raises TypeError for an object of another class as the program runs.
from contextlib import ExitStack


class LacksExit:
    def __enter__(self) -> None:
        pass


with ExitStack() as stack:
    stack.enter_context(LacksExit())
