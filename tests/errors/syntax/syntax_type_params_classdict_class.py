# error: syntax_type_params_classdict_class.py:2: error: reserved name '__classdict__' cannot be used for type parameter
class Box[__classdict__]:
    def __init__(self, v: __classdict__) -> None:
        self.v = v


print(Box(1).v)
