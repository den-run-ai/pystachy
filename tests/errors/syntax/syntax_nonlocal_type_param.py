# error: syntax_nonlocal_type_param.py:4: error: nonlocal binding not allowed for type parameter 'T'
def f[T]():
    def g():
        nonlocal T


print("ran")
