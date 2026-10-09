# error: syntax_nonlocal_type_param_method.py:5: error: nonlocal binding not allowed for type parameter 'T'
class C[T]:
    def m(self):
        def k():
            nonlocal T
        return k


print("ran")
