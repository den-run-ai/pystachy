# error: nested_def.py:3: error: a class inside a function is not supported
def f() -> None:
    class G:
        pass
