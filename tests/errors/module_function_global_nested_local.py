# error: module_function_global_nested_local.py:15: error: 'helper' is bound both as a variable and as a function, class or import (not supported)
# A def nested in a function assigns the module's function helper as a global: the error is
# that assignment's, not the enclosing function's own local of the same name


def helper() -> int:
    return 1


def outer() -> int:
    helper = 2

    def inner() -> None:
        global helper
        helper = 3
    inner()
    return helper


print(outer())
