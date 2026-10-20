# error: syntax_type_params_starred_def_typevar.py:3: error: invalid syntax
class Box:
    def get[T = *int](self, x: T) -> T:
        return x


print("ran")
