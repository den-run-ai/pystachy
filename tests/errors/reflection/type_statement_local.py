# error: type_statement_local.py:3: error: 'type' statements are only supported at a module's top level, for a name that no other statement binds
def f() -> int:
    type Local = list[int]
    x: Local = [1]
    return len(x)


print(f())
