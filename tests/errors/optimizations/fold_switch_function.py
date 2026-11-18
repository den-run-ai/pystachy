# error: fold_switch_function.py:9: error: name 'Missing' is not defined
# if NAME: right after NAME = False is decided only in module code: in a function, what the
# branch that does not run binds still makes it local, so both branches are compiled.


def f() -> str:
    mypyc = False
    if mypyc:
        kind = Missing
    else:
        kind = "native"
    return kind


print(f())
