# error: fold_flag_in_function.py:9: error: module 'pathlib' is not supported
# TYPE_CHECKING = False is a constant only for the module code after it: a function, which may run
# before it, tests it as it runs.
TYPE_CHECKING = False


def f() -> None:
    if TYPE_CHECKING:
        import pathlib
    print("f")


f()
