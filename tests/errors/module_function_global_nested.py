# error: module_function_global_nested.py:13: error: 'helper' is bound both as a variable and as a function, class or import (not supported)
# A def nested in a function assigns the module's function helper as a global: the error is
# that assignment's, not the enclosing function's def


def helper() -> int:
    return 1


def outer() -> None:
    def inner() -> None:
        global helper
        helper = 3
    inner()


outer()
