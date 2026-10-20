# TYPE_CHECKING = False that a function's global statement rebinds is no constant: its test runs
# (tests/programs/optimizations/fold_false.py).
TYPE_CHECKING = False


def enable() -> None:
    global TYPE_CHECKING
    TYPE_CHECKING = True


enable()
if TYPE_CHECKING:
    import loader.helper
