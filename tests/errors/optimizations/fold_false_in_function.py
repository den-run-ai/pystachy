# error: fold_false_in_function.py:6: error: module 'pathlib' is not supported
# "if False:" is decided only in module code: in a function, what its branch binds is still local
# to it, so the branch is compiled.
def f() -> None:
    if False:
        import pathlib
    print("f")


f()
